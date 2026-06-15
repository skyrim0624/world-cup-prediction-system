from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.daily_update import (
    DEFAULT_DAILY_STATUS_PATH,
    DEFAULT_DAILY_LOCK_PATH,
    load_feed_specs,
    load_score_source_specs,
    run_daily_update,
    write_daily_update_failure_status,
)
from backend.event_review import RAW_NEWS_PATH
from backend.snapshot import DEFAULT_SNAPSHOT_PATH


def main() -> None:
    parser = argparse.ArgumentParser(description="执行世界杯预测系统每日更新流程")
    parser.add_argument("--raw-news-path", type=Path, default=RAW_NEWS_PATH)
    parser.add_argument("--snapshot", type=Path, default=DEFAULT_SNAPSHOT_PATH)
    parser.add_argument("--feed-config", type=Path, default=None)
    parser.add_argument("--score-config", type=Path, default=None)
    parser.add_argument("--simulations", type=int, default=50_000)
    parser.add_argument("--report", type=Path, default=None)
    parser.add_argument("--status", type=Path, default=DEFAULT_DAILY_STATUS_PATH)
    parser.add_argument("--lock", type=Path, default=DEFAULT_DAILY_LOCK_PATH)
    parser.add_argument("--lock-timeout", type=float, default=0)
    args = parser.parse_args()

    try:
        feed_specs = load_feed_specs(args.feed_config) if args.feed_config else []
        score_specs = load_score_source_specs(args.score_config) if args.score_config else []
        report = run_daily_update(
            raw_news_path=args.raw_news_path,
            snapshot_path=args.snapshot,
            feed_specs=feed_specs,
            score_specs=score_specs,
            simulation_count=args.simulations,
            status_path=args.status,
            lock_path=args.lock,
            lock_timeout_seconds=args.lock_timeout,
        )
    except Exception as error:
        write_daily_update_failure_status(args.status, error)
        print(f"日更流程失败: {error}", file=sys.stderr)
        raise SystemExit(1) from error

    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("日更流程完成")
    if report["status"] == "skipped":
        print("已有日更任务运行，跳过本次执行")
        print(f"锁文件: {report['lockPath']}")
        return
    print(f"新闻新增: {report['feeds']['imported']}")
    print(f"新闻跳过: {report['feeds']['skipped']}")
    print(f"赛果更新: {report['scores']['updated']}")
    print(f"赛果锁定: {report['scores']['finished']}")
    print(f"进行中更新: {report['scores']['live']}")
    print(f"快照路径: {report['snapshot']['path']}")
    print(f"模拟次数: {report['snapshot']['simulationCount']}")
    print(f"锁定赛果: {report['snapshot']['lockedResults']}")


if __name__ == "__main__":
    main()
