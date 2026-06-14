from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

from .data import DATA_DIR, Fixture, TeamProfile
from .team_history import (
    build_scoring_environment,
    calculate_elite_performance_metrics,
    calculate_recent_form_metrics,
    load_team_match_history,
)
from .squad_matchup import build_star_power_profile

TEAM_ADVANCED_METRICS_PATH = DATA_DIR / "team-advanced-metrics.json"
TEAM_STRENGTH_LAYER_IDS = [
    "baseStrength",
    "recentForm",
    "elitePerformance",
    "squadContinuity",
    "attackQuality",
    "defenseQuality",
    "goalkeeperQuality",
    "tacticalProfile",
]
PROFESSIONAL_GAP_IDS = [
    "eventXgData",
    "playerModel",
    "lineupPrediction",
    "eliteSampleAdjustment",
    "marketCalibration",
    "backtesting",
    "probabilityCalibration",
    "bayesianUpdating",
    "tacticalMatchup",
]
ADJUSTMENT_KEYS = ("attack", "defense", "goalkeeper", "path", "squad")
HISTORICAL_ELO_BLEND = 0.45
MAX_HISTORICAL_ELO_DELTA = 85.0


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


def nested_metrics(row: dict[str, Any], section: str) -> dict[str, Any]:
    value = row.get(section)
    return value if isinstance(value, dict) else {}


def has_any_metric(section: dict[str, Any], keys: tuple[str, ...]) -> bool:
    return any(numeric(section.get(key)) is not None for key in keys)


def build_layer(
    layer_id: str,
    label: str,
    status: str,
    source: str,
    metrics: dict[str, float | int | str | None],
    adjustments: dict[str, float] | None = None,
    missing: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "id": layer_id,
        "label": label,
        "status": status,
        "source": source,
        "metrics": metrics,
        "adjustments": adjustments or zero_adjustments(),
        "missing": missing or [],
    }


def load_team_metric_rows(path: Path = TEAM_ADVANCED_METRICS_PATH) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict) and isinstance(payload.get("teams"), dict):
        return payload["teams"]
    if isinstance(payload, dict):
        return payload
    raise ValueError("team-advanced-metrics.json 必须是对象或包含 teams 对象")


def finished_team_matches(team_key: str, fixtures: list[Fixture]) -> list[Fixture]:
    return [
        fixture
        for fixture in fixtures
        if fixture.status == "finished"
        and fixture.home_score is not None
        and fixture.away_score is not None
        and team_key in {fixture.home, fixture.away}
    ]


def result_for_team(team_key: str, fixture: Fixture) -> tuple[int, int, int]:
    if fixture.home == team_key:
        goals_for = int(fixture.home_score or 0)
        goals_against = int(fixture.away_score or 0)
    else:
        goals_for = int(fixture.away_score or 0)
        goals_against = int(fixture.home_score or 0)
    points = 3 if goals_for > goals_against else 1 if goals_for == goals_against else 0
    return goals_for, goals_against, points


def base_strength_layer(team: TeamProfile, row: dict[str, Any], history_team: dict[str, Any] | None = None) -> dict[str, Any]:
    section = nested_metrics(row, "baseStrength")
    history_team = history_team or {}
    historical_elo = numeric(history_team.get("latestElo"))
    metrics = {
        "elo": team.elo,
        "historicalElo": historical_elo,
        "historicalEloDate": history_team.get("latestEloDate") if isinstance(history_team.get("latestEloDate"), str) else None,
        "fifaRating": numeric(section.get("fifaRating")),
        "independentElo": numeric(section.get("independentElo")),
        "opponentAdjustedRating": numeric(section.get("opponentAdjustedRating")),
        "marketPrior": numeric(section.get("marketPrior")),
    }
    adjustment = zero_adjustments()
    external_rating = metrics["opponentAdjustedRating"] or metrics["independentElo"] or metrics["fifaRating"] or historical_elo
    if isinstance(external_rating, float):
        delta = clamp((external_rating - team.elo) / 120, -1.5, 1.5)
        adjustment["attack"] = round(delta * 0.35, 2)
        adjustment["defense"] = round(delta * 0.35, 2)
        adjustment["path"] = round(delta * 0.15, 2)
    if isinstance(section.get("source"), str):
        source = section["source"]
    elif historical_elo is not None:
        source = "teams_json_and_cc0_history_elo"
    else:
        source = "teams_json_verified_seed"
    return build_layer("baseStrength", "基础强度层", "active", source, metrics, adjustment)


def apply_historical_elo_baseline(
    teams: dict[str, TeamProfile],
    history: dict[str, Any],
    blend: float = HISTORICAL_ELO_BLEND,
) -> dict[str, TeamProfile]:
    history_teams = history.get("teams") if isinstance(history.get("teams"), dict) else {}
    adjusted: dict[str, TeamProfile] = {}
    for team_key, team in teams.items():
        history_team = history_teams.get(team_key) if isinstance(history_teams.get(team_key), dict) else {}
        latest_elo = numeric(history_team.get("latestElo")) if isinstance(history_team, dict) else None
        if latest_elo is None:
            adjusted[team_key] = team
            continue
        delta = clamp((latest_elo - team.elo) * blend, -MAX_HISTORICAL_ELO_DELTA, MAX_HISTORICAL_ELO_DELTA)
        adjusted[team_key] = replace(team, elo=int(round(team.elo + delta)))
    return adjusted


def recent_form_layer(
    team_key: str,
    fixtures: list[Fixture],
    teams: dict[str, TeamProfile],
    history: dict[str, Any],
    scoring_environment: dict[str, Any] | None = None,
) -> dict[str, Any]:
    metrics = calculate_recent_form_metrics(team_key, history, teams, scoring_environment=scoring_environment)
    if metrics.get("status") == "active":
        return build_layer(
            "recentForm",
            "近期战绩层",
            "active",
            "cc0_international_results",
            {
                "matches": metrics["matches"],
                "pointsPerMatch": metrics["pointsPerMatch"],
                "expectedPointsPerMatch": metrics["expectedPointsPerMatch"],
                "opponentAdjustedPointsPerMatch": metrics["opponentAdjustedPointsPerMatch"],
                "weightedGoalDifferencePerMatch": metrics["weightedGoalDifferencePerMatch"],
                "weightedGoalsForPerMatch": metrics["weightedGoalsForPerMatch"],
                "weightedGoalsAgainstPerMatch": metrics["weightedGoalsAgainstPerMatch"],
                "goalBaseline": metrics["goalBaseline"],
            },
            metrics["adjustments"],
        )

    matches = finished_team_matches(team_key, fixtures)
    if not matches:
        return build_layer("recentForm", "近期战绩层", "neutral", "neutral_no_finished_fixtures", {"matches": 0})

    goals_for = goals_against = points = 0
    for fixture in matches:
        fixture_for, fixture_against, fixture_points = result_for_team(team_key, fixture)
        goals_for += fixture_for
        goals_against += fixture_against
        points += fixture_points

    played = len(matches)
    gf_per_match = goals_for / played
    ga_per_match = goals_against / played
    gd_per_match = gf_per_match - ga_per_match
    points_per_match = points / played
    adjustment = zero_adjustments()
    adjustment["attack"] = round(clamp((gf_per_match - 1.35) * 0.45 + max(gd_per_match, 0) * 0.2, -0.8, 0.8), 2)
    adjustment["defense"] = round(clamp((1.15 - ga_per_match) * 0.45 + max(gd_per_match, 0) * 0.15, -0.8, 0.8), 2)
    adjustment["path"] = round(clamp((points_per_match - 1.5) * 0.18, -0.35, 0.35), 2)
    return build_layer(
        "recentForm",
        "近期战绩层",
        "active",
        "official_finished_fixtures",
        {
            "matches": played,
            "pointsPerMatch": round(points_per_match, 2),
            "goalsForPerMatch": round(gf_per_match, 2),
            "goalsAgainstPerMatch": round(ga_per_match, 2),
            "goalDifferencePerMatch": round(gd_per_match, 2),
        },
        adjustment,
    )


def elite_performance_layer(row: dict[str, Any]) -> dict[str, Any]:
    section = nested_metrics(row, "elitePerformance")
    keys = ("top20XgDiff", "top20ResultIndex", "daysSinceTop20Win")
    if not has_any_metric(section, keys):
        return build_layer(
            "elitePerformance",
            "强队对抗层",
            "missing",
            "missing_authorized_data",
            {},
            missing=list(keys),
        )
    xg_diff = numeric(section.get("top20XgDiff")) or 0.0
    result_index = numeric(section.get("top20ResultIndex")) or 0.5
    days_since_win = numeric(section.get("daysSinceTop20Win"))
    recency = 0.0 if days_since_win is None else clamp((365 - days_since_win) / 365, -1.0, 1.0)
    adjustment = zero_adjustments()
    adjustment["attack"] = round(clamp(xg_diff * 0.55 + (result_index - 0.5) * 0.7, -1.6, 1.6), 2)
    adjustment["defense"] = round(clamp(xg_diff * 0.35 + (result_index - 0.5) * 0.45, -1.2, 1.2), 2)
    adjustment["path"] = round(clamp(recency * 0.35, -0.35, 0.35), 2)
    return build_layer("elitePerformance", "强队对抗层", "active", source_for(section), section_metrics(section, keys), adjustment)


def elite_performance_history_layer(
    team_key: str,
    teams: dict[str, TeamProfile],
    history: dict[str, Any],
    row: dict[str, Any],
) -> dict[str, Any]:
    section = nested_metrics(row, "elitePerformance")
    if has_any_metric(section, ("top20XgDiff", "top20ResultIndex", "daysSinceTop20Win")):
        return elite_performance_layer(row)
    metrics = calculate_elite_performance_metrics(team_key, history, teams)
    if metrics.get("status") != "active":
        return build_layer(
            "elitePerformance",
            "强队对抗层",
            "missing",
            "missing_authorized_or_history_data",
            {"eliteThreshold": metrics.get("eliteThreshold"), "eliteMatches": metrics.get("eliteMatches", 0)},
            missing=["top20XgDiff", "top20ResultIndex", "daysSinceTop20Win"],
        )
    return build_layer(
        "elitePerformance",
        "强队对抗层",
        "active",
        "cc0_international_results",
        {
            "eliteThreshold": metrics["eliteThreshold"],
            "eliteMatches": metrics["eliteMatches"],
            "eliteResultIndex": metrics["eliteResultIndex"],
            "eliteExpectedIndex": metrics["eliteExpectedIndex"],
            "eliteAdjustedIndex": metrics["eliteAdjustedIndex"],
            "eliteGoalDifferencePerMatch": metrics["eliteGoalDifferencePerMatch"],
            "eliteGoalsForPerMatch": metrics["eliteGoalsForPerMatch"],
            "eliteGoalsAgainstPerMatch": metrics["eliteGoalsAgainstPerMatch"],
            "eliteWins": metrics["eliteWins"],
            "daysSinceEliteWin": metrics["daysSinceEliteWin"],
        },
        metrics["adjustments"],
    )


def squad_continuity_layer(row: dict[str, Any]) -> dict[str, Any]:
    section = nested_metrics(row, "squadContinuity")
    keys = ("lineupContinuity", "projectedXiStrength", "injuryReplacementDropoff")
    star_profile = build_star_power_profile("_team", {"_team": row})
    if not has_any_metric(section, keys) and star_profile["status"] != "active":
        return build_layer(
            "squadContinuity",
            "阵容相似性层",
            "missing",
            "missing_authorized_data",
            {},
            missing=list(keys),
        )
    continuity = numeric(section.get("lineupContinuity")) or 0.5
    xi_strength = numeric(section.get("projectedXiStrength")) or 80
    dropoff = numeric(section.get("injuryReplacementDropoff")) or 0.0
    adjustment = zero_adjustments()
    adjustment["squad"] = round(clamp((continuity - 0.6) * 2.4 + (xi_strength - 80) / 12 - dropoff * 2.8, -2.0, 2.0), 2)
    adjustment["attack"] = round(clamp((xi_strength - 80) / 30 - dropoff * 0.8, -0.8, 0.8), 2)
    adjustment["defense"] = round(clamp((xi_strength - 80) / 34 - dropoff * 0.7, -0.8, 0.8), 2)
    if star_profile["status"] == "active":
        for key, value in star_profile["adjustments"].items():
            adjustment[key] = round(clamp(adjustment.get(key, 0.0) + float(value), -2.2, 2.2), 2)
    metrics = section_metrics(section, keys)
    metrics["starPlayers"] = len(star_profile["players"]) if star_profile["status"] == "active" else 0
    return build_layer("squadContinuity", "阵容相似性层", "active", source_for(section), metrics, adjustment)


def attack_quality_layer(row: dict[str, Any]) -> dict[str, Any]:
    section = nested_metrics(row, "attackQuality")
    keys = ("npXgFor", "shotQuality", "boxEntries", "transitionXg", "setPieceXgFor")
    if not has_any_metric(section, keys):
        return build_layer("attackQuality", "进攻质量层", "missing", "missing_authorized_data", {}, missing=list(keys))
    np_xg = numeric(section.get("npXgFor")) or 1.35
    shot_quality = numeric(section.get("shotQuality")) or 0.1
    transition_xg = numeric(section.get("transitionXg")) or 0.2
    set_piece_xg = numeric(section.get("setPieceXgFor")) or 0.18
    adjustment = zero_adjustments()
    adjustment["attack"] = round(
        clamp((np_xg - 1.35) * 1.1 + (shot_quality - 0.1) * 4.0 + (transition_xg - 0.2) * 0.55 + (set_piece_xg - 0.18) * 0.45, -2.0, 2.0),
        2,
    )
    return build_layer("attackQuality", "进攻质量层", "active", source_for(section), section_metrics(section, keys), adjustment)


def defense_quality_layer(row: dict[str, Any]) -> dict[str, Any]:
    section = nested_metrics(row, "defenseQuality")
    keys = ("npXgAgainst", "bigChancesAllowed", "transitionXgAgainst", "setPieceXgAgainst")
    if not has_any_metric(section, keys):
        return build_layer("defenseQuality", "防守质量层", "missing", "missing_authorized_data", {}, missing=list(keys))
    np_xga = numeric(section.get("npXgAgainst")) or 1.25
    big_chances = numeric(section.get("bigChancesAllowed")) or 1.3
    transition_xga = numeric(section.get("transitionXgAgainst")) or 0.22
    set_piece_xga = numeric(section.get("setPieceXgAgainst")) or 0.18
    adjustment = zero_adjustments()
    adjustment["defense"] = round(
        clamp((1.25 - np_xga) * 1.2 + (1.3 - big_chances) * 0.35 + (0.22 - transition_xga) * 0.7 + (0.18 - set_piece_xga) * 0.45, -2.0, 2.0),
        2,
    )
    return build_layer("defenseQuality", "防守质量层", "active", source_for(section), section_metrics(section, keys), adjustment)


def goalkeeper_quality_layer(row: dict[str, Any]) -> dict[str, Any]:
    section = nested_metrics(row, "goalkeeperQuality")
    keys = ("postShotXgMinusGoalsAllowed", "claimCrossRate", "sweeperActions", "penaltySaveProfile")
    if not has_any_metric(section, keys):
        return build_layer("goalkeeperQuality", "门将层", "missing", "missing_authorized_data", {}, missing=list(keys))
    psxg = numeric(section.get("postShotXgMinusGoalsAllowed")) or 0.0
    claims = numeric(section.get("claimCrossRate")) or 0.0
    sweeper = numeric(section.get("sweeperActions")) or 0.0
    adjustment = zero_adjustments()
    adjustment["goalkeeper"] = round(clamp(psxg * 2.8 + claims * 1.4 + sweeper * 0.12, -1.6, 1.6), 2)
    adjustment["defense"] = round(clamp(psxg * 0.8 + claims * 0.4, -0.6, 0.6), 2)
    return build_layer("goalkeeperQuality", "门将层", "active", source_for(section), section_metrics(section, keys), adjustment)


def tactical_profile_layer(row: dict[str, Any]) -> dict[str, Any]:
    section = nested_metrics(row, "tacticalProfile")
    keys = ("pressingIntensity", "pressResistance", "directness", "setPieceMismatch", "aerialAdvantage")
    if not has_any_metric(section, keys):
        return build_layer("tacticalProfile", "战术匹配层", "missing", "missing_authorized_data", {}, missing=list(keys))
    press = numeric(section.get("pressingIntensity")) or 0.5
    resistance = numeric(section.get("pressResistance")) or 0.5
    set_piece = numeric(section.get("setPieceMismatch")) or 0.0
    aerial = numeric(section.get("aerialAdvantage")) or 0.0
    adjustment = zero_adjustments()
    adjustment["attack"] = round(clamp((resistance - 0.5) * 0.8 + set_piece * 0.5 + aerial * 0.35, -1.0, 1.0), 2)
    adjustment["defense"] = round(clamp((press - 0.5) * 0.6 + aerial * 0.25, -0.8, 0.8), 2)
    adjustment["path"] = round(clamp(set_piece * 0.25, -0.35, 0.35), 2)
    return build_layer("tacticalProfile", "战术匹配层", "active", source_for(section), section_metrics(section, keys), adjustment)


def source_for(section: dict[str, Any]) -> str:
    source = section.get("source")
    return source if isinstance(source, str) and source else "authorized_metric_row"


def section_metrics(section: dict[str, Any], keys: tuple[str, ...]) -> dict[str, float | int | str | None]:
    return {key: numeric(section.get(key)) for key in keys}


def build_team_strength_profile(
    team_key: str,
    teams: dict[str, TeamProfile],
    fixtures: list[Fixture],
    metric_rows: dict[str, Any] | None = None,
    history: dict[str, Any] | None = None,
    scoring_environment: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rows = metric_rows or {}
    active_history = history if history is not None else load_team_match_history()
    row = rows.get(team_key) if isinstance(rows.get(team_key), dict) else {}
    history_team = active_history.get("teams", {}).get(team_key)
    if not isinstance(history_team, dict):
        history_team = {}
    team = teams[team_key]
    layers = {
        "baseStrength": base_strength_layer(team, row, history_team),
        "recentForm": recent_form_layer(team_key, fixtures, teams, active_history, scoring_environment),
        "elitePerformance": elite_performance_history_layer(team_key, teams, active_history, row),
        "squadContinuity": squad_continuity_layer(row),
        "attackQuality": attack_quality_layer(row),
        "defenseQuality": defense_quality_layer(row),
        "goalkeeperQuality": goalkeeper_quality_layer(row),
        "tacticalProfile": tactical_profile_layer(row),
    }
    adjustments = aggregate_layer_adjustments(layers)
    active_layers = len([layer for layer in layers.values() if layer["status"] == "active"])
    return {
        "team": team_key,
        "source": row.get("source") if isinstance(row.get("source"), str) else "mixed_verified_inputs",
        "coverage": round(active_layers / len(TEAM_STRENGTH_LAYER_IDS), 2),
        "layers": layers,
        "adjustments": adjustments,
        "overall": round(sum(adjustments.values()), 2),
    }


def aggregate_layer_adjustments(layers: dict[str, dict[str, Any]]) -> dict[str, float]:
    totals = zero_adjustments()
    for layer in layers.values():
        adjustments = layer.get("adjustments")
        if not isinstance(adjustments, dict):
            continue
        for key in ADJUSTMENT_KEYS:
            totals[key] += float(adjustments.get(key) or 0.0)
    return {key: round(value, 2) for key, value in totals.items()}


def build_all_team_strength_profiles(
    teams: dict[str, TeamProfile],
    fixtures: list[Fixture],
    metric_rows: dict[str, Any] | None = None,
    history: dict[str, Any] | None = None,
) -> dict[str, Any]:
    active_history = history if history is not None else load_team_match_history()
    scoring_environment = build_scoring_environment(active_history, teams)
    return {
        team_key: build_team_strength_profile(team_key, teams, fixtures, metric_rows, active_history, scoring_environment)
        for team_key in teams
    }


def aggregate_team_strength_adjustments(
    teams: dict[str, TeamProfile],
    fixtures: list[Fixture],
    metric_rows: dict[str, Any] | None = None,
    history: dict[str, Any] | None = None,
) -> dict[str, dict[str, float]]:
    profiles = build_all_team_strength_profiles(teams, fixtures, metric_rows, history)
    return {team_key: profile["adjustments"] for team_key, profile in profiles.items()}


def any_section_metric(metric_rows: dict[str, Any], section: str, keys: tuple[str, ...]) -> bool:
    for row in metric_rows.values():
        if not isinstance(row, dict):
            continue
        if has_any_metric(nested_metrics(row, section), keys):
            return True
    return False


def meta_section(metric_rows: dict[str, Any], section: str) -> dict[str, Any]:
    meta = metric_rows.get("__meta__")
    if not isinstance(meta, dict):
        return {}
    value = meta.get(section)
    return value if isinstance(value, dict) else {}


def gap_item(
    gap_id: str,
    label: str,
    active: bool,
    function_name: str,
    required_data: str,
) -> dict[str, str]:
    return {
        "id": gap_id,
        "label": label,
        "status": "active" if active else "missing",
        "modelEffect": "active" if active else "neutral",
        "functionName": function_name,
        "requiredData": required_data,
    }


def professional_gap_coverage(metric_rows: dict[str, Any] | None = None) -> list[dict[str, str]]:
    rows = metric_rows or {}
    return [
        gap_item(
            "eventXgData",
            "真实 xG / xGA / 射门质量",
            any_section_metric(rows, "attackQuality", ("npXgFor", "shotQuality"))
            or any_section_metric(rows, "defenseQuality", ("npXgAgainst",)),
            "attack_quality_layer / defense_quality_layer",
            "授权事件数据或官方 xG/xGA",
        ),
        gap_item(
            "playerModel",
            "球员级模型",
            any_section_metric(rows, "squadContinuity", ("projectedXiStrength", "injuryReplacementDropoff"))
            or any(isinstance(row, dict) and isinstance(row.get("starPlayers"), list) and bool(row.get("starPlayers")) for row in rows.values()),
            "squad_continuity_layer",
            "预计首发、球员评分、伤停替代落差",
        ),
        gap_item(
            "lineupPrediction",
            "首发预测",
            any_section_metric(rows, "squadContinuity", ("lineupContinuity",)),
            "squad_continuity_layer",
            "预计首发与历史核心阵容重合度",
        ),
        gap_item(
            "eliteSampleAdjustment",
            "强队样本修正",
            any_section_metric(rows, "elitePerformance", ("top20XgDiff", "top20ResultIndex", "daysSinceTop20Win"))
            or bool(meta_section(rows, "eliteSampleAdjustment")),
            "elite_performance_layer",
            "面对 Top 级对手的结果和过程质量",
        ),
        gap_item(
            "marketCalibration",
            "授权市场校准",
            any_section_metric(rows, "baseStrength", ("marketPrior",)),
            "base_strength_layer",
            "授权市场隐含概率或交易员先验",
        ),
        gap_item(
            "backtesting",
            "系统性回测",
            bool(meta_section(rows, "backtesting")),
            "professional_gap_coverage",
            "历史预测、赛果、Brier score、log loss",
        ),
        gap_item(
            "probabilityCalibration",
            "概率校准",
            bool(meta_section(rows, "probabilityCalibration")),
            "professional_gap_coverage",
            "校准曲线、reliability bins、温度缩放参数",
        ),
        gap_item(
            "bayesianUpdating",
            "动态贝叶斯更新",
            bool(meta_section(rows, "bayesianUpdating")),
            "professional_gap_coverage",
            "赛前/首发/实时事件分布和不确定性参数",
        ),
        gap_item(
            "tacticalMatchup",
            "战术 matchup 模型",
            any_section_metric(rows, "tacticalProfile", ("pressingIntensity", "pressResistance", "setPieceMismatch")),
            "tactical_profile_layer",
            "压迫、抗压、定位球、空中优势、阵型匹配",
        ),
    ]
