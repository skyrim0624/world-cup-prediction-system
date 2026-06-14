from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from os import environ
from pathlib import Path
from typing import Mapping
from uuid import uuid4

from .access import ACCESS_PRODUCTS, build_access_decision


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


def _read_order_store(storage_path: Path | None) -> dict[str, dict[str, object]]:
    if storage_path is None or not storage_path.exists():
        return {}
    payload = json.loads(storage_path.read_text(encoding="utf-8"))
    orders = payload.get("orders", {})
    return {str(order_id): dict(order) for order_id, order in orders.items()}


def _write_order_store(storage_path: Path | None, orders: dict[str, dict[str, object]]) -> None:
    if storage_path is None:
        return
    storage_path.parent.mkdir(parents=True, exist_ok=True)
    storage_path.write_text(json.dumps({"orders": orders}, ensure_ascii=False, indent=2), encoding="utf-8")


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


def create_payment_order(
    product_key: str,
    provider_key: str,
    env: Mapping[str, str] | None = None,
    storage_path: Path | None = None,
) -> dict[str, object]:
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
    stored_orders = _read_order_store(storage_path)
    stored_orders[str(order["orderId"])] = order
    PAYMENT_ORDERS[str(order["orderId"])] = order
    _write_order_store(storage_path, stored_orders)
    return order


def get_payment_order(order_id: str, storage_path: Path | None = None) -> dict[str, object]:
    order = PAYMENT_ORDERS.get(order_id) or _read_order_store(storage_path).get(order_id)
    if order is None:
        raise KeyError(order_id)
    PAYMENT_ORDERS[order_id] = order
    return order


def update_payment_order_status(order_id: str, status: str, storage_path: Path | None = None) -> dict[str, object]:
    stored_orders = _read_order_store(storage_path)
    order = PAYMENT_ORDERS.get(order_id) or stored_orders.get(order_id)
    if order is None:
        raise KeyError(order_id)
    updated = {
        **order,
        "status": status,
        "updatedAt": _iso(_now()),
    }
    if status == "paid":
        updated["nextAction"] = "支付已确认，可以按产品范围解锁内容。"
    PAYMENT_ORDERS[order_id] = updated
    stored_orders[order_id] = updated
    _write_order_store(storage_path, stored_orders)
    return updated


def build_order_access_decision(order_id: str, content_key: str, storage_path: Path | None = None) -> dict[str, object]:
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

    decision = build_access_decision(str(order["productKey"]), content_key, payment_configured=True)
    return {
        **decision,
        "orderId": order_id,
        "productKey": order["productKey"],
        "paymentStatus": order["status"],
    }
