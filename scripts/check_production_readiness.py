from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.daily_update import DEFAULT_DAILY_STATUS_PATH
from backend.production_health import DEFAULT_MODEL_QUALITY_REPORT_PATH, build_production_readiness
from backend.snapshot import DEFAULT_SNAPSHOT_PATH


def main() -> None:
    parser = argparse.ArgumentParser(description="检查腾讯云生产运行状态。")
    parser.add_argument("--status", type=Path, default=DEFAULT_DAILY_STATUS_PATH)
    parser.add_argument("--snapshot", type=Path, default=DEFAULT_SNAPSHOT_PATH)
    parser.add_argument("--model-quality", type=Path, default=DEFAULT_MODEL_QUALITY_REPORT_PATH)
    parser.add_argument("--now", type=str, default=None)
    parser.add_argument("--max-status-age-hours", type=int, default=2)
    parser.add_argument("--max-snapshot-age-hours", type=int, default=2)
    parser.add_argument("--allow-degraded", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    readiness = build_production_readiness(
        status_path=args.status,
        snapshot_path=args.snapshot,
        model_quality_path=args.model_quality,
        now_iso=args.now,
        max_status_age_hours=args.max_status_age_hours,
        max_snapshot_age_hours=args.max_snapshot_age_hours,
    )
    if args.json:
        print(json.dumps(readiness, ensure_ascii=False, indent=2))
    else:
        print(f"生产状态: {readiness['status']}")
        for check_id, check in readiness["checks"].items():
            print(f"- {check_id}: {check['status']} · {check['message']}")

    if readiness["status"] == "ok":
        return
    if readiness["status"] == "degraded" and args.allow_degraded:
        return
    raise SystemExit(1)


if __name__ == "__main__":
    main()
