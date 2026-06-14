from __future__ import annotations

import os
from hmac import compare_digest
from typing import Any

from fastapi import Header, HTTPException, Request


def read_scope_binding(env: Any, key: str) -> str | None:
    if env is None:
        return None
    if isinstance(env, dict):
        value = env.get(key)
    else:
        value = getattr(env, key, None)
    if value in (None, ""):
        return None
    return str(value)


def resolve_admin_token(request: Request | None = None) -> str | None:
    expected = os.environ.get("WORLD_CUP_ADMIN_TOKEN")
    if expected:
        return expected

    env = request.scope.get("env") if request is not None else None
    binding_token = read_scope_binding(env, "WORLD_CUP_ADMIN_TOKEN")
    if binding_token:
        os.environ["WORLD_CUP_ADMIN_TOKEN"] = binding_token
    return binding_token


def admin_auth_required() -> bool:
    return bool(resolve_admin_token())


async def verify_admin_token(request: Request, x_admin_token: str | None = Header(default=None)) -> None:
    expected = resolve_admin_token(request)
    if not expected:
        return
    if x_admin_token and compare_digest(x_admin_token, expected):
        return
    raise HTTPException(status_code=401, detail="缺少或错误的后台 token")
