from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


def parse_daily_update_time(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def build_daily_update_health(status: dict[str, Any] | None, now: datetime | None = None) -> dict[str, Any]:
    if status is None:
        return {"status": "missing", "label": "未执行", "hoursSinceUpdate": None, "message": "暂无日更状态"}
    if status.get("status") == "failed":
        return {
            "status": "failed",
            "label": "失败",
            "hoursSinceUpdate": None,
            "message": status.get("error", "日更执行失败"),
        }
    updated_at = parse_daily_update_time(status.get("updatedAt"))
    if updated_at is None:
        return {"status": "missing", "label": "未执行", "hoursSinceUpdate": None, "message": "暂无日更时间"}
    reference_time = now or datetime.now(UTC)
    hours_since_update = max(0, int((reference_time - updated_at).total_seconds() // 3600))
    if hours_since_update > 24:
        return {
            "status": "stale",
            "label": "过期",
            "hoursSinceUpdate": hours_since_update,
            "message": "最近一次日更超过 24 小时",
        }
    return {
        "status": "fresh",
        "label": "正常",
        "hoursSinceUpdate": hours_since_update,
        "message": "最近一次日更仍在 24 小时内",
    }
