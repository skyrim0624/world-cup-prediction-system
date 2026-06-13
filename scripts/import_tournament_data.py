from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.data import DATA_DIR
from backend.data_import import apply_tournament_data_import


def main() -> None:
    parser = argparse.ArgumentParser(description="导入世界杯球队与小组赛赛程数据")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    parser.add_argument("--backup-dir", type=Path, default=DATA_DIR / "backups")
    args = parser.parse_args()

    payload = json.loads(args.input.read_text(encoding="utf-8"))
    result = apply_tournament_data_import(args.data_dir, args.backup_dir, payload)
    print("已导入赛事数据")
    print(f"来源: {result['source']}")
    print(f"球队: {result['teamCount']}")
    print(f"赛程: {result['fixtureCount']}")
    print(f"备份: {result['backupDir']}")


if __name__ == "__main__":
    main()
