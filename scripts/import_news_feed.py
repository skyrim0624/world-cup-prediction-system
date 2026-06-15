from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.event_review import RAW_NEWS_PATH
from backend.data import NEWS_SOURCES, TEAM_PROFILES
from backend.news_feed import import_news_feed


def main() -> None:
    parser = argparse.ArgumentParser(description="导入公开新闻 Feed 到 raw-news")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--raw-news-path", type=Path, default=RAW_NEWS_PATH)
    parser.add_argument("--source", required=True)
    parser.add_argument("--team", default=None)
    args = parser.parse_args()

    result = import_news_feed(
        args.raw_news_path,
        args.input.read_text(encoding="utf-8"),
        source=args.source,
        team=args.team,
        known_sources=set(NEWS_SOURCES),
        team_aliases={
            key: (profile.name, profile.code, key, key.replace("-", " "), key.replace("-", ""))
            for key, profile in TEAM_PROFILES.items()
        },
    )
    print("已导入新闻 Feed")
    print(f"新增: {result['imported']}")
    print(f"跳过: {result['skipped']}")


if __name__ == "__main__":
    main()
