from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .data import DATA_DIR


AUDIT_LOG_PATH = DATA_DIR / "admin-audit.jsonl"


def append_admin_audit(
    action: str,
    target_id: str,
    details: dict[str, Any] | None = None,
    path: Path = AUDIT_LOG_PATH,
) -> dict[str, Any]:
    entry = {
        "time": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "targetId": target_id,
        "details": details or {},
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def read_recent_admin_audit(path: Path = AUDIT_LOG_PATH, limit: int = 8) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    rows = [json.loads(line) for line in lines[-limit:] if line.strip()]
    return list(reversed(rows))
