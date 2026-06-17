from __future__ import annotations

import os
import sys
from pathlib import Path

import asgi
from workers import WorkerEntrypoint, env


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.main import app  # noqa: E402


def env_value(env, key: str) -> str | None:
    if hasattr(env, key):
        return str(getattr(env, key))
    try:
        value = env[key]
    except Exception:
        return None
    return str(value) if value is not None else None


def sync_cloudflare_env(runtime_env) -> None:
    keys = [
        "WORLD_CUP_ADMIN_TOKEN",
        "WORLD_CUP_PUBLIC_API_BASE_URL",
        "WORLD_CUP_PUBLIC_WEB_BASE_URL",
        "CUSTOMER_WECHAT_JSAPI_PAY_CREATE_URL",
        "CUSTOMER_WECHAT_JSAPI_PAY_STATUS_URL",
        "CUSTOMER_WECHAT_JSAPI_PAY_NOTIFY_SECRET",
        "CUSTOMER_WECHAT_JSAPI_PAY_AUTH_TOKEN",
        "CUSTOMER_WECHAT_JSAPI_PAY_AUTH_HEADER",
        "CUSTOMER_WECHAT_JSAPI_PAY_HEADERS_JSON",
        "CUSTOMER_WECHAT_JSAPI_PAY_CREATE_METHOD",
        "CUSTOMER_WECHAT_JSAPI_PAY_STATUS_METHOD",
        "CUSTOMER_WECHAT_NATIVE_PAY_CREATE_URL",
        "CUSTOMER_WECHAT_NATIVE_PAY_STATUS_URL",
        "CUSTOMER_WECHAT_NATIVE_PAY_NOTIFY_SECRET",
        "CUSTOMER_WECHAT_NATIVE_PAY_NOTIFY_URL",
        "CUSTOMER_WECHAT_NATIVE_PAY_AUTH_TOKEN",
        "CUSTOMER_WECHAT_NATIVE_PAY_AUTH_HEADER",
        "CUSTOMER_WECHAT_NATIVE_PAY_HEADERS_JSON",
        "CUSTOMER_WECHAT_NATIVE_PAY_CREATE_METHOD",
        "CUSTOMER_WECHAT_NATIVE_PAY_STATUS_METHOD",
        "CUSTOMER_ALIPAY_QR_PAY_CREATE_URL",
        "CUSTOMER_ALIPAY_QR_PAY_STATUS_URL",
        "CUSTOMER_ALIPAY_QR_PAY_NOTIFY_SECRET",
        "CUSTOMER_ALIPAY_QR_PAY_AUTH_TOKEN",
        "CUSTOMER_ALIPAY_QR_PAY_AUTH_HEADER",
        "CUSTOMER_ALIPAY_QR_PAY_HEADERS_JSON",
        "CUSTOMER_ALIPAY_QR_PAY_CREATE_METHOD",
        "CUSTOMER_ALIPAY_QR_PAY_STATUS_METHOD",
    ]
    for key in keys:
        value = env_value(runtime_env, key)
        if value:
            os.environ[key] = value


sync_cloudflare_env(env)


class Default(WorkerEntrypoint):
    async def fetch(self, request):
        sync_cloudflare_env(self.env)
        return await asgi.fetch(app, request, self.env)
