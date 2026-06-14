from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .model import build_match_prediction


DEFAULT_SNAPSHOT_PATH = Path(__file__).with_name("snapshots") / "latest-match-prediction.json"
REQUIRED_MODEL_META_FIELDS = {"simulationCount", "changeBaseline", "lockedResults", "dataset", "events"}
REQUIRED_SNAPSHOT_FIELDS = {"dailyMovers"}
FACTOR_REASON_LABELS = {
    "attack": "状态盘",
    "defense": "状态盘",
    "goalkeeper": "边际盘",
    "path": "路径盘",
    "squad": "人员盘",
}
TOURNAMENT_REASON_LABELS = {
    "final": "决赛概率",
    "semifinal": "四强概率",
    "quarterfinal": "八强概率",
}


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


def signed_number(value: float) -> str:
    return f"{value:+.1f}"


def signed_percent(value: float) -> str:
    return f"{value:+.1f}%"


def model_meta(payload: dict[str, object]) -> dict[str, object]:
    meta = payload.get("modelMeta")
    return meta if isinstance(meta, dict) else {}


def numeric_meta_value(payload: dict[str, object], key: str) -> float:
    value = model_meta(payload).get(key)
    return float(value) if isinstance(value, (int, float)) else 0.0


def event_applied_count(payload: dict[str, object]) -> int:
    events = model_meta(payload).get("events")
    if not isinstance(events, dict):
        return 0
    applied = events.get("applied")
    return int(applied) if isinstance(applied, (int, float)) else 0


def team_factor_values(payload: dict[str, object], team_key: str) -> dict[str, float]:
    values: dict[str, float] = {}
    meta = model_meta(payload)
    for field in ("factorImpacts", "fixtureContextImpacts"):
        impact_map = meta.get(field)
        if not isinstance(impact_map, dict):
            continue
        team_impacts = impact_map.get(team_key)
        if not isinstance(team_impacts, dict):
            continue
        for factor, value in team_impacts.items():
            if isinstance(value, (int, float)):
                values[factor] = values.get(factor, 0.0) + float(value)
    return values


def factor_reason_lines(current: dict[str, object], previous: dict[str, object], team_key: str, change: float) -> list[str]:
    current_values = team_factor_values(current, team_key)
    previous_values = team_factor_values(previous, team_key)
    plate_deltas: dict[str, float] = {}
    for factor in set(current_values) | set(previous_values):
        label = FACTOR_REASON_LABELS.get(factor)
        if label is None:
            continue
        delta = current_values.get(factor, 0.0) - previous_values.get(factor, 0.0)
        plate_deltas[label] = plate_deltas.get(label, 0.0) + delta

    aligned = []
    for label, delta in plate_deltas.items():
        if abs(delta) < 0.05:
            continue
        if change > 0 and delta <= 0:
            continue
        if change < 0 and delta >= 0:
            continue
        direction = "上调" if delta > 0 else "下调"
        aligned.append((abs(delta), f"{label}{direction} {signed_number(delta)}"))
    aligned.sort(reverse=True)
    return [line for _, line in aligned]


def tournament_reason_lines(current_team: dict[str, object], previous_team: dict[str, object], change: float) -> list[str]:
    current_tournament = current_team.get("tournament")
    previous_tournament = previous_team.get("tournament")
    if not isinstance(current_tournament, dict) or not isinstance(previous_tournament, dict):
        return []
    lines = []
    for key, label in TOURNAMENT_REASON_LABELS.items():
        current_value = current_tournament.get(key)
        previous_value = previous_tournament.get(key)
        if not isinstance(current_value, (int, float)) or not isinstance(previous_value, (int, float)):
            continue
        delta = round(float(current_value) - float(previous_value), 1)
        if abs(delta) < 0.1:
            continue
        if change > 0 and delta <= 0:
            continue
        if change < 0 and delta >= 0:
            continue
        verb = "上升" if delta > 0 else "下降"
        lines.append((abs(delta), f"{label}{verb} {signed_percent(delta)}"))
    lines.sort(reverse=True)
    return [line for _, line in lines]


def meta_reason_lines(current: dict[str, object], previous: dict[str, object]) -> list[str]:
    lines = []
    locked_delta = int(numeric_meta_value(current, "lockedResults") - numeric_meta_value(previous, "lockedResults"))
    if locked_delta > 0:
        lines.append(f"已完赛果新增 {locked_delta} 场，路径重新模拟")

    applied_delta = event_applied_count(current) - event_applied_count(previous)
    if applied_delta > 0:
        lines.append(f"可入模型事件新增 {applied_delta} 条")
    elif applied_delta < 0:
        lines.append(f"可入模型事件减少 {abs(applied_delta)} 条")
    return lines


def build_mover_reasons(
    team_key: str,
    current: dict[str, object],
    previous: dict[str, object],
    current_team: dict[str, object],
    previous_team: dict[str, object],
    change: float,
) -> list[str]:
    reasons = [
        *factor_reason_lines(current, previous, team_key, change),
        *tournament_reason_lines(current_team, previous_team, change),
        *meta_reason_lines(current, previous),
    ]
    if reasons:
        return reasons
    return [f"冠军概率较上一快照{'上调' if change > 0 else '下调'} {signed_percent(change)}"]


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
        reasons = build_mover_reasons(team_key, current, previous, current_team, previous_team, change)
        items.append(
            {
                "team": team_key,
                "name": current_team.get("name", team_key),
                "code": current_team.get("code", team_key[:3].upper()),
                "previousChampion": round(previous_champion, 1),
                "currentChampion": round(current_champion, 1),
                "change": change,
                "direction": "up" if change > 0 else "down",
                "reason": reasons[0],
                "reasons": reasons,
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
