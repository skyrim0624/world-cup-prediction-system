from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from . import data as data_state
from .event_review import RAW_NEWS_PATH
from .model import reload_model_data
from .news_feed import import_news_feed
from .snapshot import DEFAULT_SNAPSHOT_PATH, write_prediction_snapshot

DEFAULT_DAILY_STATUS_PATH = RAW_NEWS_PATH.parent / "daily-update-status.json"


@dataclass(frozen=True)
class FeedSpec:
    input_path: Path
    source: str
    team: str | None = None


def ensure_json_array_file(path: Path) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("[]\n", encoding="utf-8")


def load_feed_specs(config_path: Path) -> list[FeedSpec]:
    rows = json.loads(config_path.read_text(encoding="utf-8"))
    specs: list[FeedSpec] = []
    for row in rows:
        input_path = Path(row["input"])
        if not input_path.is_absolute():
            input_path = config_path.parent / input_path
        specs.append(FeedSpec(input_path=input_path, source=row["source"], team=row.get("team")))
    return specs


def run_daily_update(
    raw_news_path: Path = RAW_NEWS_PATH,
    snapshot_path: Path = DEFAULT_SNAPSHOT_PATH,
    feed_specs: list[FeedSpec] | None = None,
    simulation_count: int = 50_000,
    fixtures_path: Path | None = None,
    status_path: Path | None = None,
) -> dict[str, Any]:
    ensure_json_array_file(raw_news_path)
    total_imported = 0
    total_skipped = 0
    feed_reports = []

    for spec in feed_specs or []:
        result = import_news_feed(
            raw_news_path,
            spec.input_path.read_text(encoding="utf-8"),
            source=spec.source,
            team=spec.team,
            known_sources=set(data_state.NEWS_SOURCES),
        )
        total_imported += result["imported"]
        total_skipped += result["skipped"]
        feed_reports.append(
            {
                "input": str(spec.input_path),
                "source": spec.source,
                "team": spec.team,
                **result,
            }
        )

    reload_model_data(raw_news_path=raw_news_path, fixtures_path=fixtures_path)
    snapshot = write_prediction_snapshot(snapshot_path, simulation_count)
    model_meta = snapshot["modelMeta"]
    report = {
        "status": "success",
        "feeds": {
            "imported": total_imported,
            "skipped": total_skipped,
            "items": feed_reports,
        },
        "snapshot": {
            "path": str(snapshot_path),
            "simulationCount": model_meta["simulationCount"],
            "lockedResults": model_meta["lockedResults"],
            "liveMatches": model_meta["liveMatches"],
            "events": model_meta["events"],
            "movers": snapshot.get("dailyMovers", {}).get("summary", {}),
        },
        "updatedAt": snapshot["updatedAt"],
    }
    if status_path is not None:
        status_path.parent.mkdir(parents=True, exist_ok=True)
        status_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def read_daily_update_status(path: Path = DEFAULT_DAILY_STATUS_PATH) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def write_daily_update_failure_status(path: Path, error: Exception) -> dict[str, Any]:
    payload = {
        "status": "failed",
        "updatedAt": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "error": str(error),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload
