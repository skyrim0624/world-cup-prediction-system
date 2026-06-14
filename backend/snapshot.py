from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .model import build_match_prediction


DEFAULT_SNAPSHOT_PATH = Path(__file__).with_name("snapshots") / "latest-match-prediction.json"
REQUIRED_MODEL_META_FIELDS = {"simulationCount", "changeBaseline", "lockedResults", "dataset", "events"}
REQUIRED_SNAPSHOT_FIELDS = {"dailyMovers"}


def previous_snapshot_path_for(path: Path = DEFAULT_SNAPSHOT_PATH) -> Path:
    return path.with_name(f"previous-{path.name}")


def read_prediction_snapshot(path: Path = DEFAULT_SNAPSHOT_PATH) -> dict[str, object] | None:
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    model_meta = payload.get("modelMeta")
    if not isinstance(model_meta, dict):
        return None
    if not REQUIRED_MODEL_META_FIELDS.issubset(model_meta):
        return None
    if not REQUIRED_SNAPSHOT_FIELDS.issubset(payload):
        return None
    return payload


def team_champion_map(payload: dict[str, object]) -> dict[str, dict[str, object]]:
    teams = payload.get("teams")
    if not isinstance(teams, list):
        return {}
    result = {}
    for item in teams:
        if not isinstance(item, dict):
            continue
        key = item.get("key")
        tournament = item.get("tournament")
        if not isinstance(key, str) or not isinstance(tournament, dict):
            continue
        champion = tournament.get("champion")
        if not isinstance(champion, (int, float)):
            continue
        result[key] = item
    return result


def build_probability_movers(
    current: dict[str, object],
    previous: dict[str, object] | None,
    limit: int = 8,
) -> dict[str, object]:
    if previous is None:
        return {
            "baseline": "no_previous_snapshot",
            "items": [],
            "summary": {"up": 0, "down": 0, "largestUp": None, "largestDown": None},
        }

    current_teams = team_champion_map(current)
    previous_teams = team_champion_map(previous)
    items = []
    for team_key, current_team in current_teams.items():
        previous_team = previous_teams.get(team_key)
        if previous_team is None:
            continue
        current_champion = float(current_team["tournament"]["champion"])
        previous_champion = float(previous_team["tournament"]["champion"])
        change = round(current_champion - previous_champion, 1)
        if abs(change) < 0.05:
            continue
        items.append(
            {
                "team": team_key,
                "name": current_team.get("name", team_key),
                "code": current_team.get("code", team_key[:3].upper()),
                "previousChampion": round(previous_champion, 1),
                "currentChampion": round(current_champion, 1),
                "change": change,
                "direction": "up" if change > 0 else "down",
                "reason": "较上一快照上调" if change > 0 else "较上一快照下调",
            }
        )

    items.sort(key=lambda item: (abs(float(item["change"])), float(item["currentChampion"])), reverse=True)
    largest_up = next((item for item in items if item["direction"] == "up"), None)
    largest_down = next((item for item in items if item["direction"] == "down"), None)
    return {
        "baseline": "previous_snapshot",
        "items": items[:limit],
        "summary": {
            "up": len([item for item in items if item["direction"] == "up"]),
            "down": len([item for item in items if item["direction"] == "down"]),
            "largestUp": largest_up,
            "largestDown": largest_down,
        },
    }


def write_prediction_snapshot(
    path: Path = DEFAULT_SNAPSHOT_PATH,
    simulation_count: int = 50_000,
    previous_path: Path | None = None,
) -> dict[str, object]:
    previous = read_prediction_snapshot(path)
    prediction = build_match_prediction(simulation_count)
    payload = {
        **prediction,
        "snapshotMeta": {
            "type": "match-prediction",
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "path": str(path),
        },
    }
    payload["dailyMovers"] = build_probability_movers(payload, previous)
    path.parent.mkdir(parents=True, exist_ok=True)
    if previous is not None:
        target_previous_path = previous_path or previous_snapshot_path_for(path)
        target_previous_path.parent.mkdir(parents=True, exist_ok=True)
        target_previous_path.write_text(json.dumps(previous, ensure_ascii=False, indent=2), encoding="utf-8")
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload
