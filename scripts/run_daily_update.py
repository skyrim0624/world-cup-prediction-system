from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.daily_update import DEFAULT_DAILY_STATUS_PATH, load_feed_specs, run_daily_update
from backend.event_review import RAW_NEWS_PATH
from backend.snapshot import DEFAULT_SNAPSHOT_PATH


def main() -> None:
    parser = argparse.ArgumentParser(description="执行世界杯预测系统每日更新流程")
    parser.add_argument("--raw-news-path", type=Path, default=RAW_NEWS_PATH)
    parser.add_argument("--snapshot", type=Path, default=DEFAULT_SNAPSHOT_PATH)
    parser.add_argument("--feed-config", type=Path, default=None)
    parser.add_argument("--simulations", type=int, default=50_000)
    parser.add_argument("--report", type=Path, default=None)
    parser.add_argument("--status", type=Path, default=DEFAULT_DAILY_STATUS_PATH)
    args = parser.parse_args()

    feed_specs = load_feed_specs(args.feed_config) if args.feed_config else []
    report = run_daily_update(
        raw_news_path=args.raw_news_path,
        snapshot_path=args.snapshot,
        feed_specs=feed_specs,
        simulation_count=args.simulations,
        status_path=args.status,
    )

    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("日更流程完成")
    print(f"新闻新增: {report['feeds']['imported']}")
    print(f"新闻跳过: {report['feeds']['skipped']}")
    print(f"快照路径: {report['snapshot']['path']}")
    print(f"模拟次数: {report['snapshot']['simulationCount']}")
    print(f"锁定赛果: {report['snapshot']['lockedResults']}")


if __name__ == "__main__":
    main()
