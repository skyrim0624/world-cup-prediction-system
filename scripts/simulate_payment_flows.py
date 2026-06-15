from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.payments import (
    PAYMENT_ORDERS,
    build_order_access_decision,
    create_payment_order,
    get_payment_order,
    handle_payment_notification,
    refresh_payment_order_status,
)


PUBLIC_API_BASE_URL = "http://127.0.0.1:8000"
PUBLIC_WEB_BASE_URL = "http://127.0.0.1:5173"
NATIVE_NOTIFY_URL = "https://zhugejunshi.com/api/app-payment/wechat/notify"


PAYMENT_ENV = {
    "WORLD_CUP_PUBLIC_API_BASE_URL": PUBLIC_API_BASE_URL,
    "WORLD_CUP_PUBLIC_WEB_BASE_URL": PUBLIC_WEB_BASE_URL,
    "CUSTOMER_WECHAT_JSAPI_PAY_CREATE_URL": "mock://payment/wechat-jsapi/create",
    "CUSTOMER_WECHAT_JSAPI_PAY_STATUS_URL": "mock://payment/wechat-jsapi/status",
    "CUSTOMER_WECHAT_JSAPI_PAY_NOTIFY_SECRET": "mock-wechat-jsapi-notify-secret",
    "CUSTOMER_WECHAT_JSAPI_PAY_AUTH_TOKEN": "mock-wechat-jsapi-token",
    "CUSTOMER_WECHAT_NATIVE_PAY_CREATE_URL": "mock://payment/wechat-native/create",
    "CUSTOMER_WECHAT_NATIVE_PAY_STATUS_URL": "mock://payment/wechat-native/status",
    "CUSTOMER_WECHAT_NATIVE_PAY_NOTIFY_SECRET": "mock-wechat-native-notify-secret",
    "CUSTOMER_WECHAT_NATIVE_PAY_AUTH_TOKEN": "mock-wechat-native-token",
    "CUSTOMER_ALIPAY_QR_PAY_CREATE_URL": "mock://payment/alipay/create",
    "CUSTOMER_ALIPAY_QR_PAY_STATUS_URL": "mock://payment/alipay/status",
    "CUSTOMER_ALIPAY_QR_PAY_NOTIFY_SECRET": "mock-alipay-notify-secret",
    "CUSTOMER_ALIPAY_QR_PAY_AUTH_TOKEN": "mock-alipay-token",
}


PROVIDER_EXPECTATIONS = {
    "wechat_jsapi": {
        "productKey": "single_match",
        "paymentMethod": "jsapi",
        "notifyUrl": f"{PUBLIC_API_BASE_URL}/api/payments/notify/wechat_jsapi",
        "status": "SUCCESS",
        "transactionId": "mock_wx_jsapi_tx_001",
    },
    "wechat_native": {
        "productKey": "single_match",
        "paymentMethod": "native",
        "notifyUrl": NATIVE_NOTIFY_URL,
        "status": "SUCCESS",
        "transactionId": "mock_wx_native_tx_001",
    },
    "alipay_qr": {
        "productKey": "tournament_pass",
        "paymentMethod": "scan_qr",
        "notifyUrl": f"{PUBLIC_API_BASE_URL}/api/payments/notify/alipay_qr",
        "status": "TRADE_SUCCESS",
        "transactionId": "mock_alipay_trade_001",
    },
}


def _assert_customer_payload(url: str, payload: Mapping[str, object], headers: Mapping[str, str]) -> str:
    provider = str(payload.get("provider") or "")
    expectation = PROVIDER_EXPECTATIONS.get(provider)
    if expectation is None:
        raise AssertionError(f"未知模拟支付渠道: {provider}")
    if payload.get("paymentMethod") != expectation["paymentMethod"]:
        raise AssertionError(f"{provider} paymentMethod 错误: {payload.get('paymentMethod')}")
    if payload.get("notifyUrl") != expectation["notifyUrl"]:
        raise AssertionError(f"{provider} notifyUrl 错误: {payload.get('notifyUrl')}")
    if not str(payload.get("returnUrl") or "").startswith(f"{PUBLIC_WEB_BASE_URL}/payment/pending?orderId="):
        raise AssertionError(f"{provider} returnUrl 缺失或错误")
    if int(payload.get("amountCents") or 0) <= 0:
        raise AssertionError(f"{provider} amountCents 缺失")
    if not str(headers.get("Authorization") or "").startswith("Bearer mock-"):
        raise AssertionError(f"{provider} Authorization 头缺失")
    if provider == "wechat_jsapi" and payload.get("openid") != "mock-openid-001":
        raise AssertionError("wechat_jsapi 必须携带 openid 模拟值")
    if provider == "wechat_native" and url != PAYMENT_ENV["CUSTOMER_WECHAT_NATIVE_PAY_CREATE_URL"]:
        raise AssertionError("wechat_native 创建订单 URL 错误")
    return provider


def _mock_customer_request(url: str, payload: Mapping[str, object], headers: Mapping[str, str], method: str = "POST") -> Mapping[str, object]:
    if method != "POST":
        raise AssertionError(f"模拟支付网关只接受 POST，当前为 {method}")
    if url.endswith("/create"):
        provider = _assert_customer_payload(url, payload, headers)
        if provider == "wechat_jsapi":
            return {
                "status": "pending",
                "jsapiParams": {
                    "appId": "wx-mock-app",
                    "timeStamp": "1781500000",
                    "nonceStr": "mock-nonce",
                    "package": "prepay_id=mock-wx-jsapi-prepay",
                    "signType": "RSA",
                    "paySign": "mock-jsapi-signature",
                },
                "prepayId": "mock-wx-jsapi-prepay",
            }
        if provider == "wechat_native":
            return {
                "status": "NOTPAY",
                "code_url": "weixin://wxpay/bizpayurl?pr=mock-native",
                "prepay_id": "mock-wx-native-prepay",
            }
        return {
            "trade_status": "WAIT_BUYER_PAY",
            "qrCodeUrl": "https://mock-pay.example/alipay/qr.png",
            "trade_no": "mock-alipay-precreate",
        }
    if url.endswith("/status"):
        order_id = str(payload.get("orderId") or "")
        if not order_id.startswith("pay_"):
            raise AssertionError("查单 payload 缺少 orderId")
        if "wechat-jsapi" in url:
            return {"status": "SUCCESS", "transactionId": "mock_wx_jsapi_tx_001"}
        if "wechat-native" in url:
            return {"status": "SUCCESS", "transactionId": "mock_wx_native_tx_001"}
        if "alipay" in url:
            return {"trade_status": "TRADE_SUCCESS", "trade_no": "mock_alipay_trade_001"}
    raise AssertionError(f"未知模拟支付 URL: {url}")


def _signed_notify(provider: str, order_id: str, storage_path: Path) -> dict[str, object]:
    expectation = PROVIDER_EXPECTATIONS[provider]
    secret_key = f"CUSTOMER_{'ALIPAY_QR' if provider == 'alipay_qr' else provider.upper()}_PAY_NOTIFY_SECRET"
    secret = PAYMENT_ENV[secret_key]
    body = json.dumps(
        {
            "outTradeNo": order_id,
            "status": expectation["status"],
            "transactionId": expectation["transactionId"],
        },
        separators=(",", ":"),
    ).encode("utf-8")
    signature = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return handle_payment_notification(
        provider,
        body,
        {"X-Payment-Signature": signature},
        env=PAYMENT_ENV,
        storage_path=storage_path,
    )


def _metadata_for_provider(provider: str) -> dict[str, object]:
    metadata: dict[str, object] = {
        "contentKey": "match_prediction",
        "matchKey": "netherlands-japan",
        "homeTeam": "netherlands",
        "awayTeam": "japan",
        "homeName": "荷兰",
        "awayName": "日本",
    }
    if provider == "wechat_jsapi":
        metadata["wechatOpenId"] = "mock-openid-001"
    return metadata


def simulate_payment_flows() -> dict[str, object]:
    PAYMENT_ORDERS.clear()
    flows: list[dict[str, object]] = []
    with TemporaryDirectory() as temp_dir:
        storage_path = Path(temp_dir) / "payment-orders.json"
        for provider, expectation in PROVIDER_EXPECTATIONS.items():
            order = create_payment_order(
                str(expectation["productKey"]),
                provider,
                metadata=_metadata_for_provider(provider),
                env=PAYMENT_ENV,
                storage_path=storage_path,
                payment_requester=_mock_customer_request,
            )
            synced = refresh_payment_order_status(
                str(order["orderId"]),
                env=PAYMENT_ENV,
                storage_path=storage_path,
                payment_requester=_mock_customer_request,
            )
            decision = build_order_access_decision(
                str(order["orderId"]),
                "match_prediction" if expectation["productKey"] == "single_match" else "tournament_probabilities",
                match_key="netherlands-japan" if expectation["productKey"] == "single_match" else None,
                storage_path=storage_path,
            )
            notify_result = _signed_notify(provider, str(order["orderId"]), storage_path)
            notified_order = get_payment_order(str(order["orderId"]), storage_path)
            flow = {
                "provider": provider,
                "paymentMethod": order["paymentMethod"],
                "statusAfterCreate": order["status"],
                "statusAfterSync": synced["status"],
                "statusAfterNotify": notified_order["status"],
                "hasJsapiParams": bool(order.get("jsapiParams")),
                "hasQrCode": bool(order.get("qrCodeUrl")),
                "accessAllowed": bool(decision["allowed"]),
                "notifyOk": bool(notify_result.get("ok")),
            }
            if flow["statusAfterSync"] != "paid" or flow["statusAfterNotify"] != "paid":
                raise AssertionError(f"{provider} 未完成支付模拟")
            if not flow["accessAllowed"]:
                raise AssertionError(f"{provider} 支付后未解锁内容")
            if not flow["notifyOk"]:
                raise AssertionError(f"{provider} 回调验签模拟失败")
            flows.append(flow)
    return {"ok": True, "flows": flows}


def main() -> None:
    parser = argparse.ArgumentParser(description="本地模拟微信 JSAPI、微信 Native 和支付宝支付全链路。")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    result = simulate_payment_flows()
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    print("本地支付模拟通过")
    for flow in result["flows"]:
        artifact = "JSAPI 参数" if flow["hasJsapiParams"] else "二维码"
        print(f"- {flow['provider']}: {flow['paymentMethod']} · {artifact} · 查单 paid · 回调 paid · 已解锁")


if __name__ == "__main__":
    main()
