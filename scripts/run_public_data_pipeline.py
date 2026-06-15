from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend import data as data_state
from backend.event_review import RAW_NEWS_PATH
from backend.public_data_pipeline import load_public_data_specs, run_public_data_pipeline

DEFAULT_PUBLIC_DATA_CONFIG_PATH = data_state.DATA_DIR / "public-data-sources.json"


def team_aliases() -> dict[str, tuple[str, ...]]:
    return {
        key: (profile.name, profile.code, key, key.replace("-", " "), key.replace("-", ""))
        for key, profile in data_state.TEAM_PROFILES.items()
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="执行公开网页 / RSS / 官方接口数据采集管线")
    parser.add_argument("--config", type=Path, default=DEFAULT_PUBLIC_DATA_CONFIG_PATH)
    parser.add_argument("--raw-news-path", type=Path, default=RAW_NEWS_PATH)
    parser.add_argument("--report", type=Path, default=None)
    args = parser.parse_args()

    report = run_public_data_pipeline(
        raw_news_path=args.raw_news_path,
        specs=load_public_data_specs(args.config),
        team_aliases=team_aliases(),
        known_sources=set(data_state.NEWS_SOURCES),
        source_levels={key: source.source_level for key, source in data_state.NEWS_SOURCES.items()},
    )

    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("公开数据采集完成")
    print(f"新增: {report['imported']}")
    print(f"跳过: {report['skipped']}")
    print(f"多源确认: {report['verification']['multiSource']}")
    print(f"入模/待审/忽略: {report['routing']['apply']} / {report['routing']['watch']} / {report['routing']['ignore']}")


if __name__ == "__main__":
    main()
