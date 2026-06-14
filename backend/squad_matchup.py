from __future__ import annotations

from dataclasses import replace
from typing import Any

from .data import Fixture, TeamProfile

ADJUSTMENT_KEYS = ("attack", "defense", "goalkeeper", "path", "squad")


def clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def zero_adjustments() -> dict[str, float]:
    return {key: 0.0 for key in ADJUSTMENT_KEYS}


def numeric(value: Any) -> float | None:
    if isinstance(value, bool) or value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def team_row(team_key: str, metric_rows: dict[str, Any] | None) -> dict[str, Any]:
    rows = metric_rows or {}
    value = rows.get(team_key)
    return value if isinstance(value, dict) else {}


def build_star_power_profile(team_key: str, metric_rows: dict[str, Any] | None = None) -> dict[str, Any]:
    row = team_row(team_key, metric_rows)
    players = row.get("starPlayers")
    if not isinstance(players, list) or not players:
        return {
            "team": team_key,
            "status": "missing",
            "source": "missing_authorized_player_data",
            "players": [],
            "adjustments": zero_adjustments(),
        }

    adjustments = zero_adjustments()
    normalized_players = []
    for item in players:
        if not isinstance(item, dict):
            continue
        rating = numeric(item.get("rating"))
        availability = numeric(item.get("availability"))
        role = str(item.get("role") or "squad")
        if rating is None or availability is None:
            continue
        impact = clamp((rating - 80) / 10 * availability, -1.5, 1.8)
        if role in {"attack", "forward", "winger"}:
            adjustments["attack"] += impact
        elif role in {"defense", "defender", "midfield"}:
            adjustments["defense"] += impact * 0.85
        elif role in {"goalkeeper", "keeper"}:
            adjustments["goalkeeper"] += impact
        else:
            adjustments["squad"] += impact * 0.75
        adjustments["squad"] += impact * 0.25
        normalized_players.append(
            {
                "name": str(item.get("name") or "unknown"),
                "role": role,
                "rating": rating,
                "availability": availability,
                "source": str(item.get("source") or "authorized_metric_row"),
                "impact": round(impact, 2),
            }
        )

    if not normalized_players:
        return {
            "team": team_key,
            "status": "missing",
            "source": "missing_authorized_player_data",
            "players": [],
            "adjustments": zero_adjustments(),
        }

    return {
        "team": team_key,
        "status": "active",
        "source": "authorized_star_players",
        "players": normalized_players,
        "adjustments": {key: round(clamp(value, -2.0, 2.0), 2) for key, value in adjustments.items()},
    }


def tactical_section(team_key: str, metric_rows: dict[str, Any] | None) -> dict[str, Any]:
    row = team_row(team_key, metric_rows)
    value = row.get("tacticalProfile")
    return value if isinstance(value, dict) else {}


def metric_or_default(section: dict[str, Any], key: str, default: float) -> float:
    value = numeric(section.get(key))
    return default if value is None else value


def side_matchup_metrics(team: TeamProfile, opponent: TeamProfile, section: dict[str, Any], opponent_section: dict[str, Any]) -> dict[str, float]:
    pressing = metric_or_default(section, "pressingIntensity", team.defense / 100)
    resistance = metric_or_default(section, "pressResistance", team.squad / 100)
    directness = metric_or_default(section, "directness", team.attack / 100)
    set_piece = metric_or_default(section, "setPieceMismatch", (team.attack - opponent.defense) / 100)
    aerial = metric_or_default(section, "aerialAdvantage", (team.squad - opponent.squad) / 100)
    opponent_press = metric_or_default(opponent_section, "pressingIntensity", opponent.defense / 100)
    opponent_resistance = metric_or_default(opponent_section, "pressResistance", opponent.squad / 100)
    return {
        "attackVsDefense": round((team.attack - opponent.defense) / 20, 3),
        "pressVsBuildout": round(pressing - opponent_resistance, 3),
        "buildoutVsPress": round(resistance - opponent_press, 3),
        "directnessEdge": round(directness - opponent.defense / 100, 3),
        "setPieceEdge": round(set_piece, 3),
        "aerialEdge": round(aerial, 3),
        "goalkeeperDrag": round((opponent.goalkeeper - 80) / 20, 3),
    }


def side_adjustments(metrics: dict[str, float]) -> dict[str, float]:
    adjustments = zero_adjustments()
    adjustments["attack"] = round(
        clamp(
            metrics["attackVsDefense"] * 0.55
            + metrics["buildoutVsPress"] * 0.65
            + metrics["directnessEdge"] * 0.35
            + metrics["setPieceEdge"] * 0.45
            + metrics["aerialEdge"] * 0.25
            - metrics["goalkeeperDrag"] * 0.25,
            -1.4,
            1.4,
        ),
        2,
    )
    adjustments["defense"] = round(clamp(metrics["pressVsBuildout"] * 0.45 + metrics["aerialEdge"] * 0.15, -0.8, 0.8), 2)
    adjustments["path"] = round(clamp(metrics["setPieceEdge"] * 0.18 + metrics["aerialEdge"] * 0.12, -0.35, 0.35), 2)
    return adjustments


def build_tactical_matchup(
    fixture: Fixture,
    teams: dict[str, TeamProfile],
    metric_rows: dict[str, Any] | None = None,
) -> dict[str, Any]:
    home = teams[fixture.home]
    away = teams[fixture.away]
    home_section = tactical_section(fixture.home, metric_rows)
    away_section = tactical_section(fixture.away, metric_rows)
    home_metrics = side_matchup_metrics(home, away, home_section, away_section)
    away_metrics = side_matchup_metrics(away, home, away_section, home_section)
    return {
        "source": "team_profile_matchup" if not home_section and not away_section else "verified_tactical_profile",
        "home": {
            "team": fixture.home,
            "metrics": home_metrics,
            "adjustments": side_adjustments(home_metrics),
        },
        "away": {
            "team": fixture.away,
            "metrics": away_metrics,
            "adjustments": side_adjustments(away_metrics),
        },
    }


def apply_side_adjustments(team: TeamProfile, adjustments: dict[str, float]) -> TeamProfile:
    return replace(
        team,
        attack=max(50, min(99, team.attack + int(round(adjustments.get("attack", 0))))),
        defense=max(50, min(99, team.defense + int(round(adjustments.get("defense", 0))))),
        goalkeeper=max(50, min(99, team.goalkeeper + int(round(adjustments.get("goalkeeper", 0))))),
        path=max(50, min(99, team.path + int(round(adjustments.get("path", 0))))),
        squad=max(50, min(99, team.squad + int(round(adjustments.get("squad", 0))))),
    )


def apply_matchup_adjustments(
    teams: dict[str, TeamProfile],
    fixture: Fixture,
    matchup: dict[str, Any],
) -> dict[str, TeamProfile]:
    adjusted = dict(teams)
    for side in ("home", "away"):
        side_data = matchup.get(side)
        if not isinstance(side_data, dict):
            continue
        team_key = side_data.get("team")
        if not isinstance(team_key, str) or team_key not in adjusted:
            continue
        adjustments = side_data.get("adjustments")
        if isinstance(adjustments, dict):
            adjusted[team_key] = apply_side_adjustments(adjusted[team_key], adjustments)
    return adjusted
