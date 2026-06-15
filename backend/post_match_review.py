from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .data import Fixture

DEFAULT_PREVIOUS_MATCH_PREDICTION_PATH = Path(__file__).with_name("snapshots") / "previous-latest-match-prediction.json"


def parse_score(value: object) -> tuple[int, int] | None:
    if not isinstance(value, str) or "-" not in value:
        return None
    left, right = value.split("-", 1)
    try:
        return int(left.strip()), int(right.strip())
    except ValueError:
        return None


def load_previous_match_prediction_snapshot(path: Path = DEFAULT_PREVIOUS_MATCH_PREDICTION_PATH) -> dict[str, Any] | None:
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else None


def snapshot_matches_fixture(snapshot: dict[str, Any] | None, fixture: Fixture) -> bool:
    if not isinstance(snapshot, dict):
        return False
    return snapshot.get("homeTeam") == fixture.home and snapshot.get("awayTeam") == fixture.away


def top_score_prediction(snapshot: dict[str, Any]) -> dict[str, Any] | None:
    score_outcomes = snapshot.get("scoreOutcomes")
    if not isinstance(score_outcomes, list) or not score_outcomes:
        return None
    first = score_outcomes[0]
    if not isinstance(first, dict):
        return None
    parsed = parse_score(first.get("score"))
    if parsed is None:
        return None
    return {
        "score": str(first.get("score")),
        "homeGoals": parsed[0],
        "awayGoals": parsed[1],
        "probability": first.get("probability"),
    }


def max_score_matrix_goal(snapshot: dict[str, Any]) -> int:
    score_matrix = snapshot.get("scoreMatrix")
    if not isinstance(score_matrix, list):
        return 0
    max_goal = 0
    for cell in score_matrix:
        if not isinstance(cell, dict):
            continue
        for key in ("homeGoals", "awayGoals"):
            value = cell.get(key)
            if isinstance(value, int):
                max_goal = max(max_goal, value)
    return max_goal


def review_severity(total_goal_error: int, winner_missed: bool) -> str:
    if winner_missed or total_goal_error >= 4:
        return "high"
    if total_goal_error >= 2:
        return "medium"
    return "low"


def unique(values: list[str]) -> list[str]:
    seen = set()
    result = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def build_post_match_review(fixture: Fixture, prediction_snapshot: dict[str, Any] | None = None) -> dict[str, Any]:
    if fixture.status != "finished" or fixture.home_score is None or fixture.away_score is None:
        return {
            "status": "not_applicable",
            "reason": "比赛尚未完赛，不能做赛后误差复盘。",
        }

    actual_score = f"{fixture.home_score}-{fixture.away_score}"
    if not snapshot_matches_fixture(prediction_snapshot, fixture):
        return {
            "status": "missing_prediction_baseline",
            "actualScore": actual_score,
            "reason": "没有匹配这场比赛的赛前预测快照，无法量化比分误差。",
            "targetFunctions": ["write_prediction_snapshot", "previous_snapshot_path_for"],
            "calibrationActions": ["保存每场赛前预测快照，作为赛后误差复盘基线。"],
        }

    predicted = top_score_prediction(prediction_snapshot)
    if predicted is None:
        return {
            "status": "missing_score_prediction",
            "actualScore": actual_score,
            "reason": "赛前快照缺少可解析的最可能比分。",
            "targetFunctions": ["score_outcomes_for_match"],
            "calibrationActions": ["确保每场赛前快照写入 scoreOutcomes。"],
        }

    actual_home = int(fixture.home_score)
    actual_away = int(fixture.away_score)
    predicted_home = int(predicted["homeGoals"])
    predicted_away = int(predicted["awayGoals"])
    total_goal_error = abs((actual_home + actual_away) - (predicted_home + predicted_away))
    home_goal_error = actual_home - predicted_home
    away_goal_error = actual_away - predicted_away
    predicted_margin = predicted_home - predicted_away
    actual_margin = actual_home - actual_away
    winner_missed = (predicted_margin > 0) != (actual_margin > 0) if predicted_margin != 0 and actual_margin != 0 else predicted_margin != actual_margin

    root_causes: list[str] = []
    target_functions: list[str] = []
    calibration_actions: list[str] = []

    if max(actual_home, actual_away) >= 5 and max(predicted_home, predicted_away) < 5:
        root_causes.append("large_score_tail_underestimated")
        target_functions.extend(["expected_goals", "score_distribution_from_lambdas"])
        calibration_actions.append("为强弱悬殊场加入大胜尾部校准，放宽强队进球上限或加入大比分混合分布。")

    matrix_max_goal = max_score_matrix_goal(prediction_snapshot)
    if matrix_max_goal and max(actual_home, actual_away) > matrix_max_goal:
        root_causes.append("score_matrix_truncated_tail")
        target_functions.append("score_matrix_for_match")
        calibration_actions.append("比分矩阵展示范围不能固定停在 4 球，应按强弱差动态扩展到 7 球以上。")

    if total_goal_error >= 3:
        root_causes.append("total_goals_underestimated")
        target_functions.extend(["expected_goals", "goal_markets_for_match"])
        calibration_actions.append("总进球市场需要读取高悬殊场的 over tail，不只看 2.5 球。")

    if actual_away > predicted_away and predicted_away == 0:
        root_causes.append("underdog_goal_tail_underestimated")
        target_functions.append("score_distribution_from_lambdas")
        calibration_actions.append("弱队进球不能只按均值压低，要保留反击、定位球和垃圾时间进球尾部。")

    if not root_causes:
        root_causes.append("normal_score_variance")
        calibration_actions.append("误差在常规比分波动范围内，暂不需要调整函数。")

    severity = review_severity(total_goal_error, winner_missed)
    return {
        "status": "reviewed",
        "actualScore": actual_score,
        "predictedTopScore": predicted["score"],
        "predictedTopProbability": predicted.get("probability"),
        "homeGoalError": home_goal_error,
        "awayGoalError": away_goal_error,
        "totalGoalError": total_goal_error,
        "winnerMissed": winner_missed,
        "severity": severity,
        "rootCauses": unique(root_causes),
        "targetFunctions": unique(target_functions),
        "calibrationActions": unique(calibration_actions),
        "summary": (
            f"赛前最可能比分为 {predicted['score']}，实际为 {actual_score}。"
            f"主要误差来自总进球低估 {total_goal_error} 球和大比分尾部不足。"
        ),
    }
