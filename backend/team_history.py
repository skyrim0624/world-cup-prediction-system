from __future__ import annotations

import json
from datetime import date, datetime
from math import exp, factorial, log
from pathlib import Path
from typing import Any

from .data import DATA_DIR, TeamProfile

DEFAULT_TEAM_MATCH_HISTORY_PATH = DATA_DIR / "team-match-history.json"
OFFICIAL_MATCH_WEIGHT = 1.18
FRIENDLY_MATCH_WEIGHT = 0.82
MAX_BACKTEST_GOALS = 7


def clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def load_team_match_history(path: Path = DEFAULT_TEAM_MATCH_HISTORY_PATH) -> dict[str, Any]:
    if not path.exists():
        return {
            "meta": {
                "source": "missing",
                "license": "missing",
                "scoredMatches": 0,
                "matchedTeams": 0,
            },
            "teams": {},
            "matches": [],
        }
    return json.loads(path.read_text(encoding="utf-8"))


def team_match_rows(team_key: str, history: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [
        row
        for row in history.get("matches", [])
        if row.get("home") == team_key or row.get("away") == team_key
    ]
    return sorted(rows, key=lambda row: row["date"])


def parse_match_date(value: str) -> date:
    return datetime.fromisoformat(value).date()


def match_weight(row: dict[str, Any]) -> float:
    tournament = str(row.get("tournament") or "")
    if tournament == "Friendly":
        return FRIENDLY_MATCH_WEIGHT
    return OFFICIAL_MATCH_WEIGHT


def side_values(team_key: str, row: dict[str, Any]) -> dict[str, float | str | bool]:
    is_home = row.get("home") == team_key
    goals_for = int(row["homeScore"] if is_home else row["awayScore"])
    goals_against = int(row["awayScore"] if is_home else row["homeScore"])
    opponent = row.get("away") if is_home else row.get("home")
    own_elo = float(row["homeEloBefore"] if is_home else row["awayEloBefore"])
    opponent_elo = float(row["awayEloBefore"] if is_home else row["homeEloBefore"])
    points = 3 if goals_for > goals_against else 1 if goals_for == goals_against else 0
    return {
        "opponent": opponent,
        "goalsFor": goals_for,
        "goalsAgainst": goals_against,
        "points": points,
        "goalDifference": goals_for - goals_against,
        "ownEloBefore": own_elo,
        "opponentEloBefore": opponent_elo,
        "neutral": bool(row.get("neutral")),
        "tournament": str(row.get("tournament") or ""),
        "date": str(row.get("date") or ""),
    }


def expected_points_for_match(own_elo: float, opponent_elo: float, neutral: bool) -> float:
    home_adjustment = 0.0 if neutral else 25.0
    win_probability = 1 / (1 + 10 ** (-((own_elo - opponent_elo) + home_adjustment) / 400))
    draw_probability = clamp(0.29 - abs(own_elo - opponent_elo) / 2600, 0.18, 0.31)
    return 3 * win_probability * (1 - draw_probability) + draw_probability


def empty_adjustments() -> dict[str, float]:
    return {"attack": 0.0, "defense": 0.0, "goalkeeper": 0.0, "path": 0.0, "squad": 0.0}


def calculate_recent_form_metrics(
    team_key: str,
    history: dict[str, Any],
    teams: dict[str, TeamProfile],
    window_matches: int = 18,
) -> dict[str, Any]:
    rows = team_match_rows(team_key, history)[-window_matches:]
    if not rows:
        return {
            "status": "neutral",
            "source": "cc0_international_results",
            "matches": 0,
            "adjustments": empty_adjustments(),
        }

    weighted_points = weighted_expected = weighted_gd = weighted_gf = weighted_ga = total_weight = 0.0
    for index, row in enumerate(rows):
        values = side_values(team_key, row)
        recency_weight = 0.72 ** (len(rows) - 1 - index)
        weight = recency_weight * match_weight(row)
        expected_points = expected_points_for_match(
            float(values["ownEloBefore"]),
            float(values["opponentEloBefore"]),
            bool(values["neutral"]),
        )
        weighted_points += float(values["points"]) * weight
        weighted_expected += expected_points * weight
        weighted_gd += float(values["goalDifference"]) * weight
        weighted_gf += float(values["goalsFor"]) * weight
        weighted_ga += float(values["goalsAgainst"]) * weight
        total_weight += weight

    points_per_match = weighted_points / total_weight
    expected_points_per_match = weighted_expected / total_weight
    adjusted_points = points_per_match - expected_points_per_match
    gd_per_match = weighted_gd / total_weight
    gf_per_match = weighted_gf / total_weight
    ga_per_match = weighted_ga / total_weight
    adjustments = empty_adjustments()
    adjustments["attack"] = round(clamp((gf_per_match - 1.35) * 0.55 + max(adjusted_points, 0) * 0.35, -1.4, 1.4), 2)
    adjustments["defense"] = round(clamp((1.15 - ga_per_match) * 0.55 + max(adjusted_points, 0) * 0.25, -1.4, 1.4), 2)
    adjustments["path"] = round(clamp(adjusted_points * 0.22 + gd_per_match * 0.08, -0.65, 0.65), 2)
    return {
        "status": "active",
        "source": "cc0_international_results",
        "matches": len(rows),
        "pointsPerMatch": round(points_per_match, 3),
        "expectedPointsPerMatch": round(expected_points_per_match, 3),
        "opponentAdjustedPointsPerMatch": round(adjusted_points, 3),
        "weightedGoalDifferencePerMatch": round(gd_per_match, 3),
        "weightedGoalsForPerMatch": round(gf_per_match, 3),
        "weightedGoalsAgainstPerMatch": round(ga_per_match, 3),
        "adjustments": adjustments,
    }


def elite_threshold(history: dict[str, Any], percentile: float = 0.25) -> float:
    ratings = []
    for row in history.get("matches", []):
        ratings.append(float(row.get("homeEloBefore", 1500)))
        ratings.append(float(row.get("awayEloBefore", 1500)))
    if not ratings:
        return 1700.0
    ratings.sort()
    index = int(len(ratings) * (1 - percentile))
    return ratings[min(len(ratings) - 1, max(0, index))]


def calculate_elite_performance_metrics(
    team_key: str,
    history: dict[str, Any],
    teams: dict[str, TeamProfile],
    elite_percentile: float = 0.25,
    window_years: int = 6,
) -> dict[str, Any]:
    threshold = elite_threshold(history, elite_percentile)
    rows = []
    latest_date: date | None = None
    cutoff_year = 2026 - window_years
    for row in team_match_rows(team_key, history):
        values = side_values(team_key, row)
        match_date = parse_match_date(str(values["date"]))
        if match_date.year < cutoff_year:
            continue
        latest_date = match_date if latest_date is None or match_date > latest_date else latest_date
        if float(values["opponentEloBefore"]) >= threshold:
            rows.append((row, values, match_date))
    if not rows:
        return {
            "status": "missing",
            "source": "cc0_international_results",
            "eliteThreshold": round(threshold, 1),
            "eliteMatches": 0,
            "adjustments": empty_adjustments(),
        }

    points = expected = gd = gf = ga = wins = 0.0
    latest_elite_win: date | None = None
    for row, values, match_date in rows:
        weight = match_weight(row)
        points += float(values["points"]) * weight
        expected += expected_points_for_match(
            float(values["ownEloBefore"]),
            float(values["opponentEloBefore"]),
            bool(values["neutral"]),
        ) * weight
        gd += float(values["goalDifference"]) * weight
        gf += float(values["goalsFor"]) * weight
        ga += float(values["goalsAgainst"]) * weight
        if int(values["points"]) == 3:
            wins += 1
            latest_elite_win = match_date if latest_elite_win is None or match_date > latest_elite_win else latest_elite_win

    weight_total = sum(match_weight(row) for row, _, _ in rows)
    result_index = (points / weight_total) / 3
    expected_index = (expected / weight_total) / 3
    gd_per_match = gd / weight_total
    gf_per_match = gf / weight_total
    ga_per_match = ga / weight_total
    reference_date = latest_date or max((date_value for _, _, date_value in rows), default=date(2026, 1, 1))
    days_since_win = None if latest_elite_win is None else (reference_date - latest_elite_win).days
    recency = -0.25 if days_since_win is None else clamp((540 - days_since_win) / 540, -0.8, 0.8)
    adjusted_index = result_index - expected_index
    adjustments = empty_adjustments()
    adjustments["attack"] = round(clamp((gf_per_match - 1.15) * 0.65 + max(adjusted_index, 0) * 1.25, -1.8, 1.8), 2)
    adjustments["defense"] = round(clamp((1.2 - ga_per_match) * 0.6 + max(adjusted_index, 0) * 1.0, -1.6, 1.6), 2)
    adjustments["path"] = round(clamp(adjusted_index * 0.7 + recency * 0.35 + gd_per_match * 0.08, -0.9, 0.9), 2)
    return {
        "status": "active",
        "source": "cc0_international_results",
        "eliteThreshold": round(threshold, 1),
        "eliteMatches": len(rows),
        "eliteResultIndex": round(result_index, 3),
        "eliteExpectedIndex": round(expected_index, 3),
        "eliteAdjustedIndex": round(adjusted_index, 3),
        "eliteGoalDifferencePerMatch": round(gd_per_match, 3),
        "eliteGoalsForPerMatch": round(gf_per_match, 3),
        "eliteGoalsAgainstPerMatch": round(ga_per_match, 3),
        "eliteWins": int(wins),
        "daysSinceEliteWin": days_since_win,
        "adjustments": adjustments,
    }


def rating_probability(home_elo: float, away_elo: float, neutral: bool) -> dict[str, float]:
    home_edge = 0 if neutral else 55
    home_strength = 1 / (1 + 10 ** (-((home_elo + home_edge) - away_elo) / 400))
    draw = clamp(0.28 - abs((home_elo + home_edge) - away_elo) / 2800, 0.18, 0.31)
    home = home_strength * (1 - draw)
    away = (1 - home_strength) * (1 - draw)
    total = home + draw + away
    return {"home": home / total, "draw": draw / total, "away": away / total}


def match_outcome(row: dict[str, Any]) -> str:
    if int(row["homeScore"]) > int(row["awayScore"]):
        return "home"
    if int(row["homeScore"]) < int(row["awayScore"]):
        return "away"
    return "draw"


def brier_for(probabilities: dict[str, float], actual: str) -> float:
    return sum((probabilities[key] - (1.0 if key == actual else 0.0)) ** 2 for key in ("home", "draw", "away"))


def run_prediction_backtest(history: dict[str, Any], teams: dict[str, TeamProfile], max_matches: int = 600) -> dict[str, Any]:
    team_keys = set(teams)
    eligible = [
        row
        for row in history.get("matches", [])
        if row.get("home") in team_keys and row.get("away") in team_keys
    ]
    rows = eligible[-max_matches:]
    if not rows:
        return {"status": "missing", "evaluatedMatches": 0, "brierScore": 0, "logLoss": 0, "samples": []}

    brier_total = log_total = 0.0
    samples = []
    for row in rows:
        probabilities = rating_probability(float(row["homeEloBefore"]), float(row["awayEloBefore"]), bool(row.get("neutral")))
        actual = match_outcome(row)
        brier_total += brier_for(probabilities, actual)
        log_total += -log(max(probabilities[actual], 1e-9))
        confidence = max(probabilities.values())
        correct = actual == max(probabilities, key=lambda key: probabilities[key])
        samples.append({"confidence": confidence, "correct": correct, "actual": actual, "probability": probabilities[actual]})

    count = len(rows)
    return {
        "status": "active",
        "source": "cc0_international_results",
        "evaluatedMatches": count,
        "brierScore": round(brier_total / count, 4),
        "logLoss": round(log_total / count, 4),
        "samples": samples,
    }


def build_scoring_environment(
    history: dict[str, Any],
    teams: dict[str, TeamProfile],
    max_matches: int = 1600,
) -> dict[str, Any]:
    team_keys = set(teams)
    rows = [
        row
        for row in history.get("matches", [])
        if row.get("home") in team_keys or row.get("away") in team_keys
    ][-max_matches:]
    if not rows:
        return {
            "status": "missing",
            "source": "cc0_international_results",
            "matches": 0,
            "homeGoalsPerMatch": 1.35,
            "awayGoalsPerMatch": 1.22,
            "neutralHomeGoalsPerMatch": 1.28,
            "neutralAwayGoalsPerMatch": 1.12,
            "totalGoalsPerMatch": 2.57,
            "drawRate": 0.27,
            "homeAdvantageGoals": 0.13,
        }

    home_goals = away_goals = draws = 0
    neutral_home_goals = neutral_away_goals = neutral_count = 0
    non_neutral_home_goals = non_neutral_away_goals = non_neutral_count = 0
    for row in rows:
        home_score = int(row["homeScore"])
        away_score = int(row["awayScore"])
        home_goals += home_score
        away_goals += away_score
        if home_score == away_score:
            draws += 1
        if row.get("neutral"):
            neutral_home_goals += home_score
            neutral_away_goals += away_score
            neutral_count += 1
        else:
            non_neutral_home_goals += home_score
            non_neutral_away_goals += away_score
            non_neutral_count += 1

    match_count = len(rows)
    home_per_match = home_goals / match_count
    away_per_match = away_goals / match_count
    neutral_home = neutral_home_goals / neutral_count if neutral_count else home_per_match
    neutral_away = neutral_away_goals / neutral_count if neutral_count else away_per_match
    non_neutral_edge = (
        (non_neutral_home_goals - non_neutral_away_goals) / non_neutral_count
        if non_neutral_count
        else home_per_match - away_per_match
    )
    neutral_edge = neutral_home - neutral_away
    return {
        "status": "active",
        "source": "cc0_international_results",
        "matches": match_count,
        "neutralMatches": neutral_count,
        "homeGoalsPerMatch": round(home_per_match, 3),
        "awayGoalsPerMatch": round(away_per_match, 3),
        "neutralHomeGoalsPerMatch": round(neutral_home, 3),
        "neutralAwayGoalsPerMatch": round(neutral_away, 3),
        "totalGoalsPerMatch": round((home_goals + away_goals) / match_count, 3),
        "drawRate": round(draws / match_count, 3),
        "homeAdvantageGoals": round(non_neutral_edge - neutral_edge, 3),
    }


def poisson_probability(lam: float, goals: int) -> float:
    return (lam**goals * exp(-lam)) / factorial(goals)


def poisson_probabilities_from_elos(
    home_elo: float,
    away_elo: float,
    neutral: bool,
    scoring_environment: dict[str, Any],
) -> dict[str, float]:
    if scoring_environment.get("status") == "active" and neutral:
        base_home = float(scoring_environment.get("neutralHomeGoalsPerMatch") or 1.28)
        base_away = float(scoring_environment.get("neutralAwayGoalsPerMatch") or 1.12)
    elif scoring_environment.get("status") == "active":
        base_home = float(scoring_environment.get("homeGoalsPerMatch") or 1.35)
        base_away = float(scoring_environment.get("awayGoalsPerMatch") or 1.22)
    else:
        base_home = 1.35
        base_away = 1.22
    elo_gap = home_elo - away_elo
    home_lambda = clamp(base_home * exp(elo_gap / 760), 0.35, 3.25)
    away_lambda = clamp(base_away * exp(-elo_gap / 760), 0.35, 3.25)
    home = draw = away = 0.0
    for home_goals in range(MAX_BACKTEST_GOALS + 1):
        for away_goals in range(MAX_BACKTEST_GOALS + 1):
            probability = poisson_probability(home_lambda, home_goals) * poisson_probability(away_lambda, away_goals)
            if home_goals > away_goals:
                home += probability
            elif home_goals == away_goals:
                draw += probability
            else:
                away += probability
    total = home + draw + away
    return {
        "home": home / total,
        "draw": draw / total,
        "away": away / total,
        "expectedTotalGoals": home_lambda + away_lambda,
    }


def run_poisson_backtest(
    history: dict[str, Any],
    teams: dict[str, TeamProfile],
    scoring_environment: dict[str, Any],
    max_matches: int = 600,
) -> dict[str, Any]:
    team_keys = set(teams)
    eligible = [
        row
        for row in history.get("matches", [])
        if row.get("home") in team_keys and row.get("away") in team_keys
    ]
    rows = eligible[-max_matches:]
    if not rows:
        return {
            "status": "missing",
            "source": "cc0_international_results_poisson",
            "evaluatedMatches": 0,
            "brierScore": 0,
            "logLoss": 0,
            "totalGoalsMeanError": 0,
            "samples": [],
        }

    brier_total = log_total = total_goal_error = 0.0
    samples = []
    for row in rows:
        probabilities = poisson_probabilities_from_elos(
            float(row["homeEloBefore"]),
            float(row["awayEloBefore"]),
            bool(row.get("neutral")),
            scoring_environment,
        )
        actual = match_outcome(row)
        brier_total += brier_for(probabilities, actual)
        log_total += -log(max(probabilities[actual], 1e-9))
        actual_total_goals = int(row["homeScore"]) + int(row["awayScore"])
        total_goal_error += abs(float(probabilities["expectedTotalGoals"]) - actual_total_goals)
        confidence = max(probabilities[key] for key in ("home", "draw", "away"))
        correct = actual == max(("home", "draw", "away"), key=lambda key: probabilities[key])
        samples.append({"confidence": confidence, "correct": correct, "actual": actual, "probability": probabilities[actual]})

    count = len(rows)
    return {
        "status": "active",
        "source": "cc0_international_results_poisson",
        "evaluatedMatches": count,
        "brierScore": round(brier_total / count, 4),
        "logLoss": round(log_total / count, 4),
        "totalGoalsMeanError": round(total_goal_error / count, 4),
        "samples": samples,
    }


def build_calibration_profile(backtest: dict[str, Any], bin_count: int = 5) -> dict[str, Any]:
    samples = backtest.get("samples") or []
    if not samples:
        return {"status": "missing", "bins": [], "calibrationError": None}
    bins = []
    for index in range(bin_count):
        lower = index / bin_count
        upper = (index + 1) / bin_count
        bucket = [
            sample
            for sample in samples
            if lower <= float(sample["confidence"]) < upper or (index == bin_count - 1 and float(sample["confidence"]) <= upper)
        ]
        if not bucket:
            continue
        predicted = sum(float(sample["confidence"]) for sample in bucket) / len(bucket)
        observed = sum(1 for sample in bucket if sample["correct"]) / len(bucket)
        bins.append(
            {
                "range": [round(lower, 2), round(upper, 2)],
                "count": len(bucket),
                "predicted": round(predicted, 3),
                "observed": round(observed, 3),
                "gap": round(observed - predicted, 3),
            }
        )
    weighted_error = 0.0
    total = sum(item["count"] for item in bins)
    for item in bins:
        weighted_error += abs(float(item["gap"])) * int(item["count"]) / total
    return {
        "status": "active" if total >= 200 else "limited",
        "source": "cc0_international_results",
        "bins": bins,
        "calibrationError": round(weighted_error, 4),
    }


def normalize_probabilities(probabilities: dict[str, float]) -> dict[str, float]:
    total = sum(max(0.0, value) for value in probabilities.values())
    if total <= 0:
        return {"home": 1 / 3, "draw": 1 / 3, "away": 1 / 3}
    return {key: max(0.0, value) / total for key, value in probabilities.items()}


def calibration_bin_for(confidence: float, calibration: dict[str, Any]) -> dict[str, Any] | None:
    for item in calibration.get("bins", []) or []:
        bounds = item.get("range")
        if not isinstance(bounds, list) or len(bounds) != 2:
            continue
        lower, upper = float(bounds[0]), float(bounds[1])
        if lower <= confidence < upper or (upper >= 1.0 and confidence <= upper):
            return item
    return None


def apply_probability_calibration(
    probabilities: dict[str, float],
    calibration: dict[str, Any] | None,
) -> dict[str, float]:
    normalized = normalize_probabilities(probabilities)
    if not calibration or calibration.get("status") not in {"active", "limited"}:
        return normalized

    top_key = max(normalized, key=lambda key: normalized[key])
    confidence = normalized[top_key]
    calibration_bin = calibration_bin_for(confidence, calibration)
    if calibration_bin is None:
        return normalized

    gap = float(calibration_bin.get("gap") or 0.0)
    sample_count = int(calibration_bin.get("count") or 0)
    if sample_count < 20 or abs(gap) < 0.01:
        return normalized

    adjustment = clamp(gap * 0.5, -0.08, 0.08)
    calibrated = dict(normalized)
    calibrated[top_key] = clamp(calibrated[top_key] + adjustment, 0.02, 0.92)
    remainder_keys = [key for key in calibrated if key != top_key]
    remainder_total = sum(normalized[key] for key in remainder_keys)
    redistributed = 1.0 - calibrated[top_key]
    for key in remainder_keys:
        share = normalized[key] / remainder_total if remainder_total > 0 else 1 / len(remainder_keys)
        calibrated[key] = redistributed * share
    return normalize_probabilities(calibrated)


def calibration_application_meta(calibration: dict[str, Any] | None) -> dict[str, Any]:
    if not calibration or calibration.get("status") not in {"active", "limited"}:
        return {
            "status": "inactive",
            "source": "missing_calibration_profile",
            "detail": "没有足够回测样本，胜平负概率未做历史校准。",
        }
    return {
        "status": "active",
        "source": calibration.get("source", "cc0_international_results"),
        "detail": "胜平负概率按历史回测分桶做温和置信度校准，避免模型过度自信。",
        "calibrationError": calibration.get("calibrationError"),
        "bins": len(calibration.get("bins", []) or []),
    }
