from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from os import environ
from pathlib import Path
from typing import Callable, Mapping
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen
from uuid import uuid4

from .access import ACCESS_PRODUCTS, build_access_decision


PAYMENT_ORDER_TTL_MINUTES = 15
PAYMENT_HTTP_TIMEOUT_SECONDS = 12
PAYMENT_SIMULATION_ENV = "WORLD_CUP_PAYMENT_SIMULATION"
WECHAT_NATIVE_NOTIFY_PATH = "/api/app-payment/wechat/notify"
WECHAT_NATIVE_NOTIFY_URL = "https://zhugejunshi.com/api/app-payment/wechat/notify"

PAYMENT_PROVIDERS = {
    "wechat_jsapi": {
        "label": "微信支付",
        "paymentMethod": "jsapi",
        "paymentMethodLabel": "JSAPI 支付",
        "missingLabel": "客户微信 JSAPI 支付接口",
        "envPrefix": "CUSTOMER_WECHAT_JSAPI_PAY",
        "requiredConfig": [
            "CUSTOMER_WECHAT_JSAPI_PAY_CREATE_URL",
            "CUSTOMER_WECHAT_JSAPI_PAY_STATUS_URL",
            "CUSTOMER_WECHAT_JSAPI_PAY_NOTIFY_SECRET",
        ],
    },
    "wechat_native": {
        "label": "微信支付",
        "paymentMethod": "native",
        "paymentMethodLabel": "扫码支付",
        "missingLabel": "客户微信 Native 支付接口",
        "envPrefix": "CUSTOMER_WECHAT_NATIVE_PAY",
        "requiredConfig": [
            "CUSTOMER_WECHAT_NATIVE_PAY_CREATE_URL",
            "CUSTOMER_WECHAT_NATIVE_PAY_STATUS_URL",
            "CUSTOMER_WECHAT_NATIVE_PAY_NOTIFY_SECRET",
        ],
    },
    "alipay_qr": {
        "label": "支付宝支付",
        "paymentMethod": "scan_qr",
        "paymentMethodLabel": "扫码支付",
        "missingLabel": "客户支付宝扫码接口",
        "envPrefix": "CUSTOMER_ALIPAY_QR_PAY",
        "requiredConfig": [
            "CUSTOMER_ALIPAY_QR_PAY_CREATE_URL",
            "CUSTOMER_ALIPAY_QR_PAY_STATUS_URL",
            "CUSTOMER_ALIPAY_QR_PAY_NOTIFY_SECRET",
        ],
    },
}

PAYMENT_PROVIDER_ALIASES = {
    "wechat": "wechat_native",
    "alipay": "alipay_qr",
}

PAYMENT_ORDERS: dict[str, dict[str, object]] = {}
PaymentRequester = Callable[[str, Mapping[str, object], Mapping[str, str], str], Mapping[str, object]]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _configured(env: Mapping[str, str], required_config: list[str]) -> tuple[bool, list[str]]:
    missing = [key for key in required_config if not env.get(key)]
    return len(missing) == 0, missing


def _payment_simulation_enabled(env: Mapping[str, str]) -> bool:
    return _env_value(env, PAYMENT_SIMULATION_ENV).strip().lower() in {"1", "true", "yes", "on"}


def _product(product_key: str) -> dict[str, object]:
    product = next((item for item in ACCESS_PRODUCTS if item["key"] == product_key), None)
    if product is None:
        raise ValueError(f"未知付费产品: {product_key}")
    return product


def _provider_key(provider_key: str) -> str:
    return PAYMENT_PROVIDER_ALIASES.get(provider_key, provider_key)


def _provider(provider_key: str) -> dict[str, object]:
    provider = PAYMENT_PROVIDERS.get(_provider_key(provider_key))
    if provider is None:
        raise ValueError(f"未知支付渠道: {provider_key}")
    return provider


def _provider_env_prefix(provider: Mapping[str, object]) -> str:
    return str(provider["envPrefix"])


def _env_value(env: Mapping[str, str], key: str) -> str:
    return str(env.get(key) or "")


def _header_value(headers: Mapping[str, str], key: str) -> str:
    expected = key.lower()
    for name, value in headers.items():
        if name.lower() == expected:
            return str(value)
    return ""


def _amount_cents(amount_label: object) -> int:
    raw = str(amount_label or "").strip()
    if not raw.startswith("¥"):
        raise ValueError("付费产品暂未定价，不能创建支付订单")
    normalized = raw.replace("¥", "").replace(",", "").strip()
    major, _, minor = normalized.partition(".")
    if not major.isdigit() or (minor and not minor.isdigit()):
        raise ValueError(f"付费产品金额格式无效: {raw}")
    minor = (minor + "00")[:2]
    return int(major) * 100 + int(minor)


def _customer_headers(env: Mapping[str, str], provider: Mapping[str, object]) -> dict[str, str]:
    prefix = _provider_env_prefix(provider)
    headers = {"Content-Type": "application/json"}
    auth_token = _env_value(env, f"{prefix}_AUTH_TOKEN")
    if auth_token:
        header_name = _env_value(env, f"{prefix}_AUTH_HEADER") or "Authorization"
        header_value = auth_token if auth_token.lower().startswith(("bearer ", "basic ")) else f"Bearer {auth_token}"
        headers[header_name] = header_value
    extra_headers = _env_value(env, f"{prefix}_HEADERS_JSON")
    if extra_headers:
        try:
            parsed = json.loads(extra_headers)
        except json.JSONDecodeError:
            parsed = {}
        if isinstance(parsed, dict):
            headers.update({str(key): str(value) for key, value in parsed.items() if value is not None})
    return headers


def _http_json_request(url: str, payload: Mapping[str, object], headers: Mapping[str, str], method: str = "POST") -> Mapping[str, object]:
    method = method.upper()
    body: bytes | None = None
    request_url = url
    if method == "GET":
        query = urlencode({key: value for key, value in payload.items() if value is not None})
        request_url = f"{url}{'&' if '?' in url else '?'}{query}" if query else url
    else:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = Request(request_url, data=body, headers=dict(headers), method=method)
    with urlopen(request, timeout=PAYMENT_HTTP_TIMEOUT_SECONDS) as response:
        content = response.read().decode("utf-8")
    parsed = json.loads(content) if content else {}
    if not isinstance(parsed, dict):
        raise ValueError("客户支付接口返回不是 JSON 对象")
    return parsed


def _first_value(payload: Mapping[str, object], keys: list[str]) -> object | None:
    for key in keys:
        value = payload.get(key)
        if value not in (None, ""):
            return value
    return None


def _flatten_payment_payload(payload: Mapping[str, object]) -> dict[str, object]:
    flattened = dict(payload)
    for container_key in ("data", "result", "payload"):
        nested = payload.get(container_key)
        if isinstance(nested, dict):
            flattened.update(nested)
    return flattened


def _normalize_payment_status(value: object | None) -> str:
    if value is None:
        return "pending"
    raw = str(value).strip()
    normalized = raw.upper()
    if normalized in {"PAID", "SUCCESS", "PAY_SUCCESS", "TRADE_SUCCESS", "TRADE_FINISHED"}:
        return "paid"
    if normalized in {"PENDING", "PAYMENT_PENDING", "NOTPAY", "USERPAYING", "WAIT_BUYER_PAY"}:
        return "pending"
    if normalized in {"EXPIRED", "TIMEOUT"}:
        return "expired"
    if normalized in {"FAILED", "FAIL", "CLOSED", "CANCELLED", "CANCELED", "TRADE_CLOSED"}:
        return "failed"
    return raw.lower()


def _next_action_for_order(order: Mapping[str, object]) -> str:
    status = str(order.get("status") or "")
    if status == "paid":
        return "支付已确认，可以按产品范围解锁内容。"
    if status == "pending" and order.get("jsapiParams"):
        return "等待微信内完成支付。"
    if status == "pending" and order.get("qrCodeUrl"):
        return "等待用户扫码支付。"
    if status == "expired":
        return "订单已过期，请重新创建支付订单。"
    if status == "failed":
        return "支付失败，请重新创建支付订单。"
    return "等待客户支付接口确认。"


def _customer_notify_url(env: Mapping[str, str], provider_key: str) -> str | None:
    if provider_key == "wechat_native":
        return _env_value(env, "CUSTOMER_WECHAT_NATIVE_PAY_NOTIFY_URL") or WECHAT_NATIVE_NOTIFY_URL
    public_base = _env_value(env, "WORLD_CUP_PUBLIC_API_BASE_URL").rstrip("/")
    if not public_base:
        return None
    return f"{public_base}/api/payments/notify/{provider_key}"


def _customer_return_url(env: Mapping[str, str], order_id: str) -> str | None:
    public_base = _env_value(env, "WORLD_CUP_PUBLIC_WEB_BASE_URL").rstrip("/")
    if not public_base:
        return None
    return f"{public_base}/payment/pending?orderId={order_id}"


def _simulated_qr_code_url(provider_key: str, order_id: str) -> str:
    label = "微信模拟支付" if provider_key == "wechat_native" else "支付宝模拟支付"
    short_order_id = order_id.replace("pay_", "")[:10]
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="280" height="280" viewBox="0 0 280 280">
<rect width="280" height="280" rx="20" fill="#ffffff"/>
<rect x="20" y="20" width="240" height="240" rx="12" fill="#111111"/>
<rect x="40" y="40" width="64" height="64" fill="#ffffff"/>
<rect x="176" y="40" width="64" height="64" fill="#ffffff"/>
<rect x="40" y="176" width="64" height="64" fill="#ffffff"/>
<rect x="118" y="118" width="44" height="44" fill="#ffffff"/>
<rect x="178" y="126" width="22" height="22" fill="#ffffff"/>
<rect x="126" y="178" width="22" height="22" fill="#ffffff"/>
<text x="140" y="268" text-anchor="middle" font-family="Arial, sans-serif" font-size="14" fill="#ffffff">{label} {short_order_id}</text>
</svg>"""
    return "data:image/svg+xml;charset=utf-8," + quote(svg)


def _simulated_create_response(provider_key: str, order: Mapping[str, object]) -> dict[str, object]:
    order_id = str(order["orderId"])
    if provider_key == "wechat_jsapi":
        return {
            "status": "pending",
            "jsapiParams": {
                "appId": "wx-local-simulation",
                "timeStamp": str(int(_now().timestamp())),
                "nonceStr": f"mock-{order_id[-10:]}",
                "package": f"prepay_id=mock_{order_id}",
                "signType": "RSA",
                "paySign": "mock-pay-signature",
            },
            "prepayId": f"mock_{order_id}",
        }
    if provider_key == "wechat_native":
        return {
            "status": "NOTPAY",
            "qrCodeUrl": _simulated_qr_code_url(provider_key, order_id),
            "prepayId": f"mock_{order_id}",
        }
    return {
        "trade_status": "WAIT_BUYER_PAY",
        "qrCodeUrl": _simulated_qr_code_url(provider_key, order_id),
        "tradeNo": f"mock_{order_id}",
    }


def _simulated_status_response(provider_key: str, order: Mapping[str, object]) -> dict[str, object]:
    order_id = str(order["orderId"])
    if provider_key == "alipay_qr":
        return {"trade_status": "TRADE_SUCCESS", "trade_no": f"mock_trade_{order_id}"}
    return {"status": "SUCCESS", "transactionId": f"mock_tx_{provider_key}_{order_id[-10:]}"}


def _build_customer_create_payload(
    order: Mapping[str, object],
    product: Mapping[str, object],
    provider: Mapping[str, object],
    provider_key: str,
    env: Mapping[str, str],
) -> dict[str, object]:
    metadata = order.get("metadata") if isinstance(order.get("metadata"), dict) else {}
    description = str(product["name"])
    if metadata.get("homeName") and metadata.get("awayName"):
        description = f"{product['name']}：{metadata['homeName']} vs {metadata['awayName']}"
    payload: dict[str, object] = {
        "orderId": order["orderId"],
        "outTradeNo": order["orderId"],
        "provider": provider_key,
        "paymentMethod": provider["paymentMethod"],
        "productKey": product["key"],
        "productName": product["name"],
        "description": description,
        "amountLabel": order.get("amountLabel"),
        "amountCents": _amount_cents(order.get("amountLabel")),
        "currency": "CNY",
        "metadata": metadata,
    }
    for key in ("contentKey", "matchKey", "homeTeam", "awayTeam", "homeName", "awayName"):
        if metadata.get(key):
            payload[key] = metadata[key]
    notify_url = _customer_notify_url(env, provider_key)
    return_url = _customer_return_url(env, str(order["orderId"]))
    if notify_url:
        payload["notifyUrl"] = notify_url
    if return_url:
        payload["returnUrl"] = return_url
    if metadata.get("wechatOpenId"):
        payload["openid"] = metadata["wechatOpenId"]
    return payload


def _apply_customer_payment_response(order: Mapping[str, object], response: Mapping[str, object]) -> dict[str, object]:
    response = _flatten_payment_payload(response)
    status_source = _first_value(response, ["status", "paymentStatus", "trade_status", "tradeStatus"])
    status = _normalize_payment_status(status_source)
    updated: dict[str, object] = {
        **order,
        "status": status,
        "updatedAt": _iso(_now()),
    }
    qr_code = _first_value(response, ["qrCodeUrl", "qr_code_url", "codeUrl", "code_url", "payUrl", "pay_url", "paymentUrl", "payment_url"])
    if qr_code:
        updated["qrCodeUrl"] = str(qr_code)
    jsapi_params = _first_value(response, ["jsapiParams", "jsApiParams", "jsApiParameters", "wechatPayParams", "payParams"])
    if isinstance(jsapi_params, dict):
        updated["jsapiParams"] = jsapi_params
    provider_order_id = _first_value(response, ["providerOrderId", "provider_order_id", "prepayId", "prepay_id", "tradeNo", "trade_no"])
    if provider_order_id:
        updated["providerOrderId"] = str(provider_order_id)
    transaction_id = _first_value(response, ["transactionId", "transaction_id", "tradeNo", "trade_no"])
    if transaction_id:
        updated["transactionId"] = str(transaction_id)
    message = _first_value(response, ["message", "msg", "detail"])
    if message:
        updated["customerPaymentMessage"] = str(message)
    updated["nextAction"] = _next_action_for_order(updated)
    return updated


def _read_order_store(storage_path: Path | None) -> dict[str, dict[str, object]]:
    if storage_path is None or not storage_path.exists():
        return {}
    try:
        payload = json.loads(storage_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    orders = payload.get("orders", {})
    return {str(order_id): dict(order) for order_id, order in orders.items()}


def _write_order_store(storage_path: Path | None, orders: dict[str, dict[str, object]]) -> None:
    if storage_path is None:
        return
    try:
        storage_path.parent.mkdir(parents=True, exist_ok=True)
        storage_path.write_text(json.dumps({"orders": orders}, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        return


def _persist_order(order: dict[str, object], storage_path: Path | None) -> dict[str, object]:
    PAYMENT_ORDERS[str(order["orderId"])] = order
    stored_orders = _read_order_store(storage_path)
    stored_orders[str(order["orderId"])] = order
    _write_order_store(storage_path, stored_orders)
    return order


def build_payment_config(env: Mapping[str, str] | None = None) -> dict[str, object]:
    source = env or environ
    simulation_mode = _payment_simulation_enabled(source)
    providers = []
    for provider_key, provider in PAYMENT_PROVIDERS.items():
        configured, missing = _configured(source, provider["requiredConfig"])
        if simulation_mode:
            configured = True
            missing = []
        providers.append(
            {
                "provider": provider_key,
                "label": provider["label"],
                "paymentMethod": provider["paymentMethod"],
                "paymentMethodLabel": provider["paymentMethodLabel"],
                "integrationOwner": "customer",
                "configured": configured,
                "missingConfig": missing,
            }
        )

    return {
        "ready": any(provider["configured"] for provider in providers),
        "simulationMode": simulation_mode,
        "providers": providers,
        "disclaimer": "微信支付和支付宝仅用于解锁概率分析内容，不提供投注建议。",
    }


def create_payment_order(
    product_key: str,
    provider_key: str,
    metadata: Mapping[str, object] | None = None,
    env: Mapping[str, str] | None = None,
    storage_path: Path | None = None,
    payment_requester: PaymentRequester | None = None,
) -> dict[str, object]:
    product = _product(product_key)
    normalized_provider_key = _provider_key(provider_key)
    provider = _provider(provider_key)
    source = env or environ
    simulation_mode = _payment_simulation_enabled(source)
    configured, missing = _configured(source, provider["requiredConfig"])
    if simulation_mode:
        configured = True
        missing = []
    created_at = _now()
    expires_at = created_at + timedelta(minutes=PAYMENT_ORDER_TTL_MINUTES)
    status = "customer_interface_ready" if configured else "provider_config_required"
    next_action = "正在请求客户支付接口。" if configured else f"需要先配置{provider['missingLabel']}，才能生成真实扫码付款二维码。"

    order = {
        "orderId": f"pay_{uuid4().hex}",
        "productKey": product["key"],
        "productName": product["name"],
        "amountLabel": product.get("amountLabel", "待定价"),
        "provider": normalized_provider_key,
        "providerLabel": provider["label"],
        "paymentMethod": provider["paymentMethod"],
        "paymentMethodLabel": provider["paymentMethodLabel"],
        "integrationOwner": "customer",
        "status": status,
        "qrCodeUrl": None,
        "missingConfig": missing,
        "nextAction": next_action,
        "createdAt": _iso(created_at),
        "expiresAt": _iso(expires_at),
    }
    if metadata:
        allowed_metadata_keys = {"contentKey", "matchKey", "homeTeam", "awayTeam", "homeName", "awayName", "wechatOpenId"}
        order["metadata"] = {key: value for key, value in metadata.items() if key in allowed_metadata_keys and value}

    if configured:
        requester = payment_requester or _http_json_request
        prefix = _provider_env_prefix(provider)
        create_url = _env_value(source, f"{prefix}_CREATE_URL")
        method = _env_value(source, f"{prefix}_CREATE_METHOD") or "POST"
        payload = _build_customer_create_payload(order, product, provider, normalized_provider_key, source)
        try:
            if simulation_mode and payment_requester is None:
                response = _simulated_create_response(normalized_provider_key, order)
            else:
                response = requester(create_url, payload, _customer_headers(source, provider), method)
            order = _apply_customer_payment_response(order, response)
        except Exception as error:
            order = {
                **order,
                "status": "customer_interface_error",
                "updatedAt": _iso(_now()),
                "nextAction": "客户支付创建接口调用失败，请检查接口地址、鉴权和返回字段。",
                "customerPaymentMessage": str(error),
            }

    return _persist_order(order, storage_path)


def get_payment_order(order_id: str, storage_path: Path | None = None) -> dict[str, object]:
    order = PAYMENT_ORDERS.get(order_id) or _read_order_store(storage_path).get(order_id)
    if order is None:
        raise KeyError(order_id)
    PAYMENT_ORDERS[order_id] = order
    return order


def update_payment_order_status(order_id: str, status: str, storage_path: Path | None = None, extra: Mapping[str, object] | None = None) -> dict[str, object]:
    stored_orders = _read_order_store(storage_path)
    order = PAYMENT_ORDERS.get(order_id) or stored_orders.get(order_id)
    if order is None:
        raise KeyError(order_id)
    updated = {
        **order,
        "status": status,
        "updatedAt": _iso(_now()),
    }
    if extra:
        updated.update({key: value for key, value in extra.items() if value not in (None, "")})
    if status == "paid":
        updated["nextAction"] = "支付已确认，可以按产品范围解锁内容。"
    else:
        updated["nextAction"] = _next_action_for_order(updated)
    PAYMENT_ORDERS[order_id] = updated
    stored_orders[order_id] = updated
    _write_order_store(storage_path, stored_orders)
    return updated


def refresh_payment_order_status(
    order_id: str,
    env: Mapping[str, str] | None = None,
    storage_path: Path | None = None,
    payment_requester: PaymentRequester | None = None,
) -> dict[str, object]:
    order = get_payment_order(order_id, storage_path)
    if str(order.get("status")) in {"paid", "expired", "failed"}:
        return order
    provider = _provider(str(order["provider"]))
    source = env or environ
    if _payment_simulation_enabled(source):
        updated = _apply_customer_payment_response(order, _simulated_status_response(str(order["provider"]), order))
        return _persist_order(updated, storage_path)
    configured, _ = _configured(source, provider["requiredConfig"])
    if not configured:
        return order
    prefix = _provider_env_prefix(provider)
    status_url = _env_value(source, f"{prefix}_STATUS_URL")
    method = _env_value(source, f"{prefix}_STATUS_METHOD") or "POST"
    requester = payment_requester or _http_json_request
    payload = {
        "orderId": order_id,
        "outTradeNo": order_id,
        "providerOrderId": order.get("providerOrderId"),
        "transactionId": order.get("transactionId"),
    }
    response = requester(status_url, payload, _customer_headers(source, provider), method)
    updated = _apply_customer_payment_response(order, response)
    return _persist_order(updated, storage_path)


def _notification_secret(provider_key: str, env: Mapping[str, str]) -> str:
    provider = _provider(provider_key)
    prefix = _provider_env_prefix(provider)
    return _env_value(env, f"{prefix}_NOTIFY_SECRET")


def _verify_notification_signature(body: bytes, headers: Mapping[str, str], secret: str) -> bool:
    signature = _header_value(headers, "x-payment-signature") or _header_value(headers, "x-signature")
    if not signature or not secret:
        return False
    expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    normalized_signature = signature.removeprefix("sha256=").strip()
    return hmac.compare_digest(normalized_signature, expected)


def handle_payment_notification(
    provider_key: str,
    body: bytes,
    headers: Mapping[str, str],
    env: Mapping[str, str] | None = None,
    storage_path: Path | None = None,
) -> dict[str, object]:
    source = env or environ
    try:
        normalized_provider = _provider_key(provider_key)
        secret = _notification_secret(normalized_provider, source)
    except ValueError:
        return {"ok": False, "reason": "unknown_provider"}
    if not _verify_notification_signature(body, headers, secret):
        return {"ok": False, "reason": "invalid_signature"}
    try:
        payload = json.loads(body.decode("utf-8"))
    except json.JSONDecodeError:
        return {"ok": False, "reason": "invalid_payload"}
    if not isinstance(payload, dict):
        return {"ok": False, "reason": "invalid_payload"}
    payload = _flatten_payment_payload(payload)
    order_id = _first_value(payload, ["orderId", "order_id", "outTradeNo", "out_trade_no"])
    if not order_id:
        return {"ok": False, "reason": "missing_order_id"}
    status = _normalize_payment_status(_first_value(payload, ["status", "paymentStatus", "trade_status", "tradeStatus"]))
    extra = {
        "transactionId": _first_value(payload, ["transactionId", "transaction_id", "tradeNo", "trade_no"]),
        "providerOrderId": _first_value(payload, ["providerOrderId", "provider_order_id", "prepayId", "prepay_id"]),
        "notifiedAt": _iso(_now()),
    }
    try:
        order = update_payment_order_status(str(order_id), status, storage_path=storage_path, extra=extra)
    except KeyError:
        return {"ok": False, "reason": "unknown_order", "orderId": str(order_id)}
    return {"ok": True, "orderId": order["orderId"], "status": order["status"]}


def build_order_access_decision(order_id: str, content_key: str, match_key: str | None = None, storage_path: Path | None = None) -> dict[str, object]:
    try:
        order = get_payment_order(order_id, storage_path)
    except KeyError:
        return {
            "allowed": False,
            "reason": "unknown_order",
            "orderId": order_id,
            "productKey": None,
            "paymentStatus": None,
            "requiredProducts": [],
        }

    if order["status"] != "paid":
        return {
            "allowed": False,
            "reason": "order_not_paid",
            "orderId": order_id,
            "productKey": order["productKey"],
            "paymentStatus": order["status"],
            "requiredProducts": [],
        }

    metadata = order.get("metadata") if isinstance(order.get("metadata"), dict) else {}
    order_match_key = metadata.get("matchKey") if metadata else None
    if order["productKey"] == "single_match" and content_key == "match_prediction" and order_match_key and match_key != order_match_key:
        return {
            "allowed": False,
            "reason": "match_not_in_scope",
            "orderId": order_id,
            "productKey": order["productKey"],
            "paymentStatus": order["status"],
            "requiredProducts": ["single_match", "tournament_pass", "match_pack"],
            "matchKey": order_match_key,
        }

    decision = build_access_decision(str(order["productKey"]), content_key, payment_configured=True)
    return {
        **decision,
        "orderId": order_id,
        "productKey": order["productKey"],
        "paymentStatus": order["status"],
        "matchKey": order_match_key,
    }
