from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.data import FIXTURES, TEAM_PROFILES
from backend.team_history import (
    build_calibration_profile,
    build_scoring_environment,
    calculate_elite_performance_metrics,
    calculate_recent_form_metrics,
    load_team_match_history,
    run_prediction_backtest,
)
from backend.team_strength import build_all_team_strength_profiles, load_team_metric_rows, professional_gap_coverage

DEFAULT_OUTPUT_PATH = Path("reports/model-quality-report.json")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="生成世界杯预测模型质量报告。")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--max-backtest-matches", type=int, default=600)
    return parser.parse_args()


def team_quality_summary(history: dict[str, object]) -> dict[str, object]:
    items = {}
    for team_key in TEAM_PROFILES:
        recent = calculate_recent_form_metrics(team_key, history, TEAM_PROFILES)
        elite = calculate_elite_performance_metrics(team_key, history, TEAM_PROFILES)
        items[team_key] = {
            "name": TEAM_PROFILES[team_key].name,
            "code": TEAM_PROFILES[team_key].code,
            "recentForm": {
                key: value
                for key, value in recent.items()
                if key not in {"adjustments"}
            },
            "recentAdjustments": recent.get("adjustments", {}),
            "elitePerformance": {
                key: value
                for key, value in elite.items()
                if key not in {"adjustments"}
            },
            "eliteAdjustments": elite.get("adjustments", {}),
        }
    return items


def main() -> None:
    args = parse_args()
    history = load_team_match_history()
    metric_rows = load_team_metric_rows()
    backtest = run_prediction_backtest(history, TEAM_PROFILES, args.max_backtest_matches)
    calibration = build_calibration_profile(backtest)
    scoring_environment = build_scoring_environment(history, TEAM_PROFILES)
    report = {
        "generatedAt": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "historicalData": history.get("meta", {}),
        "backtest": {
            key: value
            for key, value in backtest.items()
            if key != "samples"
        },
        "calibration": calibration,
        "scoringEnvironment": scoring_environment,
        "professionalGapCoverage": professional_gap_coverage(
            {
                **metric_rows,
                "__meta__": {
                    "eliteSampleAdjustment": {"source": "cc0_international_results"},
                    "backtesting": backtest,
                    "probabilityCalibration": calibration,
                },
            }
        ),
        "teamStrengthLayers": build_all_team_strength_profiles(TEAM_PROFILES, FIXTURES, metric_rows, history),
        "teamQualitySummary": team_quality_summary(history),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"模型质量报告已生成: {args.output} · "
        f"回测 {backtest['evaluatedMatches']} 场 · Brier {backtest['brierScore']} · LogLoss {backtest['logLoss']}"
    )


if __name__ == "__main__":
    main()
