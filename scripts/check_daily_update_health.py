from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.admin import build_daily_update_health
from backend.daily_update import DEFAULT_DAILY_STATUS_PATH, read_daily_update_status


def parse_now(value: str | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def main() -> None:
    parser = argparse.ArgumentParser(description="检查世界杯预测系统日更状态是否新鲜")
    parser.add_argument("--status", type=Path, default=DEFAULT_DAILY_STATUS_PATH)
    parser.add_argument("--now", type=str, default=None)
    args = parser.parse_args()

    status = read_daily_update_status(args.status)
    health = build_daily_update_health(status, parse_now(args.now))
    message = f"日更健康: {health['label']} · {health['message']}"
    if health["status"] == "fresh":
        print(message)
        return
    print(message, file=sys.stderr)
    raise SystemExit(1)


if __name__ == "__main__":
    main()
