from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.snapshot import DEFAULT_SNAPSHOT_PATH, write_prediction_snapshot


def main() -> None:
    parser = argparse.ArgumentParser(description="生成世界杯预测快照")
    parser.add_argument("--simulations", type=int, default=50_000)
    parser.add_argument("--output", type=Path, default=DEFAULT_SNAPSHOT_PATH)
    args = parser.parse_args()

    payload = write_prediction_snapshot(args.output, args.simulations)
    meta = payload["modelMeta"]
    print(f"已生成预测快照: {args.output}")
    print(f"模拟次数: {meta['simulationCount']}")
    print(f"锁定赛果: {meta['lockedResults']}")


if __name__ == "__main__":
    main()
