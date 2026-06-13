from __future__ import annotations

import os
from hmac import compare_digest

from fastapi import Header, HTTPException


def admin_auth_required() -> bool:
    return bool(os.environ.get("WORLD_CUP_ADMIN_TOKEN"))


def verify_admin_token(x_admin_token: str | None = Header(default=None)) -> None:
    expected = os.environ.get("WORLD_CUP_ADMIN_TOKEN")
    if not expected:
        return
    if x_admin_token and compare_digest(x_admin_token, expected):
        return
    raise HTTPException(status_code=401, detail="缺少或错误的后台 token")
