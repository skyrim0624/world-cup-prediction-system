from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .data import DATA_DIR
from .io_utils import write_json_atomic

RAW_NEWS_PATH = DATA_DIR / "raw-news.json"
ALLOWED_REVIEW_STATUSES = {"confirmed", "multi_source", "single_source", "unverified", "rumor"}


def review_raw_news_item(
    path: Path,
    item_id: str,
    status: str,
    team: str | None = None,
) -> dict[str, Any]:
    if status not in ALLOWED_REVIEW_STATUSES:
        raise ValueError(f"不支持的审核状态: {status}")

    rows = json.loads(path.read_text(encoding="utf-8"))
    for row in rows:
        if row["id"] != item_id:
            continue
        row["status"] = status
        if team is not None:
            row["team"] = team
        write_json_atomic(path, rows)
        return row
    raise ValueError(f"找不到原始新闻: {item_id}")
