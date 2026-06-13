from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.event_review import RAW_NEWS_PATH, review_raw_news_item


def main() -> None:
    parser = argparse.ArgumentParser(description="审核原始新闻事件")
    parser.add_argument("--id", required=True)
    parser.add_argument("--status", required=True, choices=["confirmed", "multi_source", "single_source", "unverified", "rumor"])
    parser.add_argument("--team")
    parser.add_argument("--path", type=Path, default=RAW_NEWS_PATH)
    args = parser.parse_args()

    updated = review_raw_news_item(args.path, args.id, args.status, args.team)
    print(f"已更新新闻: {updated['id']}")
    print(f"状态: {updated['status']}")
    print(f"球队: {updated['team']}")


if __name__ == "__main__":
    main()
