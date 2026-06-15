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
    admin_token = env_value(runtime_env, "WORLD_CUP_ADMIN_TOKEN")
    if admin_token:
        os.environ["WORLD_CUP_ADMIN_TOKEN"] = admin_token


sync_cloudflare_env(env)


class Default(WorkerEntrypoint):
    async def fetch(self, request):
        sync_cloudflare_env(self.env)
        return await asgi.fetch(app, request, self.env)
