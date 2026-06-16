from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

from . import data as data_state
from .event_review import RAW_NEWS_PATH
from .io_utils import ProcessLockBusy, acquire_process_lock, write_json_atomic, write_text_atomic
from .model import event_summary, reload_model_data
from .news_feed import import_news_feed
from .score_feed import apply_score_source_updates
from .snapshot import DEFAULT_SNAPSHOT_PATH, write_prediction_snapshot

DEFAULT_DAILY_STATUS_PATH = RAW_NEWS_PATH.parent / "daily-update-status.json"
DEFAULT_SCORE_SOURCE_CONFIG_PATH = RAW_NEWS_PATH.parent / "score-sources.json"
DEFAULT_DAILY_LOCK_PATH = RAW_NEWS_PATH.parent / "daily-update.lock"
REQUEST_HEADERS = {"User-Agent": "world-cup-prediction-system/0.1"}


@dataclass(frozen=True)
class FeedSpec:
    source: str
    team: str | None = None
    input_path: Path | None = None
    url: str | None = None


@dataclass(frozen=True)
class ScoreSourceSpec:
    source: str
    format: str
    input_path: Path | None = None
    url: str | None = None


def ensure_json_array_file(path: Path) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    write_text_atomic(path, "[]\n")


def load_feed_specs(config_path: Path) -> list[FeedSpec]:
    rows = json.loads(config_path.read_text(encoding="utf-8"))
    specs: list[FeedSpec] = []
    for row in rows:
        input_path = Path(row["input"]) if row.get("input") else None
        if input_path is not None and not input_path.is_absolute():
            input_path = config_path.parent / input_path
        url = row.get("url")
        if input_path is None and not isinstance(url, str):
            raise ValueError("Feed 配置必须包含 input 或 url")
        specs.append(FeedSpec(source=row["source"], team=row.get("team"), input_path=input_path, url=url))
    return specs


def load_score_source_specs(config_path: Path) -> list[ScoreSourceSpec]:
    rows = json.loads(config_path.read_text(encoding="utf-8"))
    specs: list[ScoreSourceSpec] = []
    for row in rows:
        input_path = Path(row["input"]) if row.get("input") else None
        if input_path is not None and not input_path.is_absolute():
            input_path = config_path.parent / input_path
        url = row.get("url")
        if input_path is None and not isinstance(url, str):
            raise ValueError("赛果源配置必须包含 input 或 url")
        specs.append(ScoreSourceSpec(source=row["source"], format=row["format"], input_path=input_path, url=url))
    return specs


def read_feed_text(spec: FeedSpec) -> str:
    if spec.input_path is not None:
        return spec.input_path.read_text(encoding="utf-8")
    if spec.url is None:
        raise ValueError("Feed 配置缺少 input 或 url")
    with urlopen(Request(spec.url, headers=REQUEST_HEADERS), timeout=20) as response:
        return response.read().decode("utf-8", errors="replace")


def read_score_source_text(spec: ScoreSourceSpec) -> str:
    if spec.input_path is not None:
        return spec.input_path.read_text(encoding="utf-8")
    if spec.url is None:
        raise ValueError("赛果源配置缺少 input 或 url")
    with urlopen(Request(spec.url, headers=REQUEST_HEADERS), timeout=20) as response:
        return response.read().decode("utf-8", errors="replace")


def run_daily_update(
    raw_news_path: Path = RAW_NEWS_PATH,
    snapshot_path: Path = DEFAULT_SNAPSHOT_PATH,
    feed_specs: list[FeedSpec] | None = None,
    score_specs: list[ScoreSourceSpec] | None = None,
    simulation_count: int = 50_000,
    fixtures_path: Path | None = None,
    status_path: Path | None = None,
    lock_path: Path | None = None,
    lock_timeout_seconds: float = 0,
) -> dict[str, Any]:
    if lock_path is not None:
        try:
            with acquire_process_lock(lock_path, lock_timeout_seconds):
                return run_daily_update(
                    raw_news_path=raw_news_path,
                    snapshot_path=snapshot_path,
                    feed_specs=feed_specs,
                    score_specs=score_specs,
                    simulation_count=simulation_count,
                    fixtures_path=fixtures_path,
                    status_path=status_path,
                    lock_path=None,
                )
        except ProcessLockBusy:
            return {
                "status": "skipped",
                "reason": "already_running",
                "updatedAt": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                "lockPath": str(lock_path),
            }

    ensure_json_array_file(raw_news_path)
    active_fixtures_path = fixtures_path or data_state.DATA_DIR / "fixtures.json"
    total_imported = 0
    total_skipped = 0
    failed_feeds = 0
    feed_reports = []
    score_payloads = []

    for spec in feed_specs or []:
        try:
            result = import_news_feed(
                raw_news_path,
                read_feed_text(spec),
                source=spec.source,
                team=spec.team,
                known_sources=set(data_state.NEWS_SOURCES),
                team_aliases=team_aliases(),
            )
        except Exception as error:
            if spec.input_path is not None:
                raise
            failed_feeds += 1
            feed_reports.append(
                {
                    "input": None,
                    "url": spec.url,
                    "source": spec.source,
                    "team": spec.team,
                    "status": "failed",
                    "error": str(error),
                    "imported": 0,
                    "skipped": 0,
                }
            )
            continue
        total_imported += result["imported"]
        total_skipped += result["skipped"]
        feed_reports.append(
            {
                "input": str(spec.input_path) if spec.input_path is not None else None,
                "url": spec.url,
                "source": spec.source,
                "team": spec.team,
                "status": "success",
                **result,
            }
        )

    for spec in score_specs or []:
        score_payloads.append(
            {
                "input": str(spec.input_path) if spec.input_path is not None else None,
                "url": spec.url,
                "source": spec.source,
                "format": spec.format,
                "content": read_score_source_text(spec),
            }
        )

    code_to_team = {profile.code.upper(): key for key, profile in data_state.TEAM_PROFILES.items()}
    score_report = apply_score_source_updates(active_fixtures_path, score_payloads, code_to_team) if score_payloads else {
        "updated": 0,
        "finished": 0,
        "live": 0,
        "skipped": 0,
        "unknownTeams": 0,
        "items": [],
    }

    reload_model_data(raw_news_path=raw_news_path, fixtures_path=active_fixtures_path)
    events = event_summary()
    snapshot = write_prediction_snapshot(snapshot_path, simulation_count)
    model_meta = snapshot["modelMeta"]
    report = {
        "status": "success",
        "feeds": {
            "imported": total_imported,
            "skipped": total_skipped,
            "failed": failed_feeds,
            "items": feed_reports,
        },
        "scores": score_report,
        "newsVerification": {
            "rawNews": len(data_state.RAW_NEWS_ITEMS),
            "singleSource": events["singleSource"],
            "multiSource": events["multiSource"],
            "confirmed": events["confirmed"],
            "reviewRequired": events["reviewRequired"],
            "ignored": events["ignored"],
            "applied": events["applied"],
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
        write_json_atomic(status_path, report)
    return report


def team_aliases() -> dict[str, tuple[str, ...]]:
    aliases: dict[str, tuple[str, ...]] = {}
    for team_key, profile in data_state.TEAM_PROFILES.items():
        aliases[team_key] = (
            profile.name,
            profile.code,
            team_key,
            team_key.replace("-", " "),
            team_key.replace("-", ""),
        )
    return aliases


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
    write_json_atomic(path, payload)
    return payload
