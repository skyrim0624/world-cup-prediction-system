from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .model import build_match_prediction


DEFAULT_SNAPSHOT_PATH = Path(__file__).with_name("snapshots") / "latest-match-prediction.json"


def read_prediction_snapshot(path: Path = DEFAULT_SNAPSHOT_PATH) -> dict[str, object] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def write_prediction_snapshot(path: Path = DEFAULT_SNAPSHOT_PATH, simulation_count: int = 50_000) -> dict[str, object]:
    prediction = build_match_prediction(simulation_count)
    payload = {
        **prediction,
        "snapshotMeta": {
            "type": "match-prediction",
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "path": str(path),
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload
