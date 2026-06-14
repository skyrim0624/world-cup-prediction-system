from __future__ import annotations

from datetime import datetime, timedelta, timezone
from os import environ
from typing import Mapping
from uuid import uuid4

from .access import ACCESS_PRODUCTS


PAYMENT_METHOD = "scan_qr"
PAYMENT_ORDER_TTL_MINUTES = 15

PAYMENT_PROVIDERS = {
    "wechat": {
        "label": "微信支付",
        "missingLabel": "客户微信支付接口",
        "requiredConfig": [
            "CUSTOMER_WECHAT_PAY_CREATE_URL",
            "CUSTOMER_WECHAT_PAY_STATUS_URL",
            "CUSTOMER_WECHAT_PAY_NOTIFY_SECRET",
        ],
    },
    "alipay": {
        "label": "支付宝支付",
        "missingLabel": "客户支付宝接口",
        "requiredConfig": [
            "CUSTOMER_ALIPAY_PAY_CREATE_URL",
            "CUSTOMER_ALIPAY_PAY_STATUS_URL",
            "CUSTOMER_ALIPAY_PAY_NOTIFY_SECRET",
        ],
    },
}

PAYMENT_ORDERS: dict[str, dict[str, object]] = {}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _configured(env: Mapping[str, str], required_config: list[str]) -> tuple[bool, list[str]]:
    missing = [key for key in required_config if not env.get(key)]
    return len(missing) == 0, missing


def _product(product_key: str) -> dict[str, object]:
    product = next((item for item in ACCESS_PRODUCTS if item["key"] == product_key), None)
    if product is None:
        raise ValueError(f"未知付费产品: {product_key}")
    return product


def _provider(provider_key: str) -> dict[str, object]:
    provider = PAYMENT_PROVIDERS.get(provider_key)
    if provider is None:
        raise ValueError(f"未知支付渠道: {provider_key}")
    return provider


def build_payment_config(env: Mapping[str, str] | None = None) -> dict[str, object]:
    source = env or environ
    providers = []
    for provider_key, provider in PAYMENT_PROVIDERS.items():
        configured, missing = _configured(source, provider["requiredConfig"])
        providers.append(
            {
                "provider": provider_key,
                "label": provider["label"],
                "paymentMethod": PAYMENT_METHOD,
                "integrationOwner": "customer",
                "configured": configured,
                "missingConfig": missing,
            }
        )

    return {
        "ready": any(provider["configured"] for provider in providers),
        "providers": providers,
        "disclaimer": "微信支付和支付宝仅用于解锁概率分析内容，不提供投注建议。",
    }


def create_payment_order(product_key: str, provider_key: str, env: Mapping[str, str] | None = None) -> dict[str, object]:
    product = _product(product_key)
    provider = _provider(provider_key)
    source = env or environ
    configured, missing = _configured(source, provider["requiredConfig"])
    created_at = _now()
    expires_at = created_at + timedelta(minutes=PAYMENT_ORDER_TTL_MINUTES)
    status = "customer_interface_ready" if configured else "provider_config_required"
    next_action = f"{provider['missingLabel']}已配置，下一步按客户返回字段映射真实二维码。" if configured else f"需要先配置{provider['missingLabel']}，才能生成真实扫码付款二维码。"

    # NOTE: 这里不生成测试二维码，避免把未接入客户支付接口的状态误导成可付款。
    order = {
        "orderId": f"pay_{uuid4().hex}",
        "productKey": product["key"],
        "productName": product["name"],
        "amountLabel": product.get("amountLabel", "待定价"),
        "provider": provider_key,
        "providerLabel": provider["label"],
        "paymentMethod": PAYMENT_METHOD,
        "integrationOwner": "customer",
        "status": status,
        "qrCodeUrl": None,
        "missingConfig": missing,
        "nextAction": next_action,
        "createdAt": _iso(created_at),
        "expiresAt": _iso(expires_at),
    }
    PAYMENT_ORDERS[str(order["orderId"])] = order
    return order


def get_payment_order(order_id: str) -> dict[str, object]:
    order = PAYMENT_ORDERS.get(order_id)
    if order is None:
        raise KeyError(order_id)
    return order
