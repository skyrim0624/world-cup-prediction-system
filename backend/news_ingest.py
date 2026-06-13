from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .event_review import ALLOWED_REVIEW_STATUSES


def append_raw_news_item(path: Path, item: dict[str, Any]) -> dict[str, Any]:
    if item["status"] not in ALLOWED_REVIEW_STATUSES:
        raise ValueError(f"不支持的审核状态: {item['status']}")

    rows = json.loads(path.read_text(encoding="utf-8"))
    if any(row["id"] == item["id"] for row in rows):
        raise ValueError(f"原始新闻 id 已存在: {item['id']}")

    rows.append(item)
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return item
