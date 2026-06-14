import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from backend.data import TEAM_PROFILES
from backend.model import build_match_prediction
from backend.team_history import (
    DEFAULT_TEAM_MATCH_HISTORY_PATH,
    apply_probability_calibration,
    build_calibration_profile,
    build_scoring_environment,
    calculate_elite_performance_metrics,
    calculate_recent_form_metrics,
    load_team_match_history,
    run_poisson_backtest,
    run_prediction_backtest,
)


class HistoryModelPipelineTest(unittest.TestCase):
    def test_public_history_dataset_is_present_and_covers_world_cup_teams(self):
        history = load_team_match_history(DEFAULT_TEAM_MATCH_HISTORY_PATH)

        self.assertEqual(history["meta"]["license"], "CC0-1.0")
        self.assertIn("martj42/international_results", history["meta"]["source"])
        self.assertGreaterEqual(history["meta"]["scoredMatches"], 900)
        self.assertEqual(set(history["teams"]), set(TEAM_PROFILES))
        self.assertTrue(all(team["scoredMatches"] >= 8 for team in history["teams"].values()))
        self.assertTrue(all(isinstance(team.get("latestElo"), (int, float)) for team in history["teams"].values()))
        self.assertTrue(all(team.get("latestEloDate") for team in history["teams"].values()))

    def test_recent_form_uses_opponent_adjusted_real_results(self):
        history = load_team_match_history(DEFAULT_TEAM_MATCH_HISTORY_PATH)

        metrics = calculate_recent_form_metrics("brazil", history, TEAM_PROFILES, window_matches=18)

        self.assertEqual(metrics["status"], "active")
        self.assertGreaterEqual(metrics["matches"], 12)
        self.assertIn("opponentAdjustedPointsPerMatch", metrics)
        self.assertIn("weightedGoalDifferencePerMatch", metrics)
        self.assertNotEqual(metrics["adjustments"]["attack"], 0.0)

    def test_elite_performance_uses_top_opponent_real_results(self):
        history = load_team_match_history(DEFAULT_TEAM_MATCH_HISTORY_PATH)

        metrics = calculate_elite_performance_metrics("brazil", history, TEAM_PROFILES, elite_percentile=0.25)

        self.assertEqual(metrics["status"], "active")
        self.assertGreaterEqual(metrics["eliteMatches"], 3)
        self.assertIn("eliteResultIndex", metrics)
        self.assertIn("daysSinceEliteWin", metrics)
        self.assertTrue(any(value != 0.0 for value in metrics["adjustments"].values()))

    def test_backtest_and_calibration_run_on_real_history(self):
        history = load_team_match_history(DEFAULT_TEAM_MATCH_HISTORY_PATH)

        backtest = run_prediction_backtest(history, TEAM_PROFILES, max_matches=320)
        calibration = build_calibration_profile(backtest)

        self.assertGreaterEqual(backtest["evaluatedMatches"], 120)
        self.assertGreater(backtest["brierScore"], 0)
        self.assertGreater(backtest["logLoss"], 0)
        self.assertGreaterEqual(len(calibration["bins"]), 4)
        self.assertIn(calibration["status"], {"active", "limited"})

    def test_poisson_score_model_backtest_runs_on_real_history(self):
        history = load_team_match_history(DEFAULT_TEAM_MATCH_HISTORY_PATH)
        environment = build_scoring_environment(history, TEAM_PROFILES, max_matches=1600)

        backtest = run_poisson_backtest(history, TEAM_PROFILES, environment, max_matches=320)

        self.assertEqual(backtest["status"], "active")
        self.assertGreaterEqual(backtest["evaluatedMatches"], 120)
        self.assertGreater(backtest["brierScore"], 0)
        self.assertGreater(backtest["logLoss"], 0)
        self.assertIn("totalGoalsMeanError", backtest)

    def test_scoring_environment_is_estimated_from_real_history(self):
        history = load_team_match_history(DEFAULT_TEAM_MATCH_HISTORY_PATH)

        environment = build_scoring_environment(history, TEAM_PROFILES, max_matches=1600)

        self.assertEqual(environment["status"], "active")
        self.assertGreaterEqual(environment["matches"], 900)
        self.assertGreater(environment["homeGoalsPerMatch"], 0.8)
        self.assertGreater(environment["awayGoalsPerMatch"], 0.6)
        self.assertIn("neutralHomeGoalsPerMatch", environment)
        self.assertIn("drawRate", environment)

    def test_probability_calibration_adjusts_overconfident_predictions(self):
        probabilities = {"home": 0.72, "draw": 0.18, "away": 0.10}
        calibration = {
            "status": "active",
            "bins": [
                {"range": [0.6, 0.8], "count": 120, "predicted": 0.72, "observed": 0.58, "gap": -0.14}
            ],
        }

        calibrated = apply_probability_calibration(probabilities, calibration)

        self.assertAlmostEqual(sum(calibrated.values()), 1.0, places=6)
        self.assertLess(calibrated["home"], probabilities["home"])
        self.assertGreater(calibrated["draw"], probabilities["draw"])
        self.assertGreater(calibrated["away"], probabilities["away"])

    def test_prediction_meta_uses_history_backtest_and_calibration(self):
        prediction = build_match_prediction(1200)
        meta = prediction["modelMeta"]

        self.assertIn("historicalData", meta)
        self.assertGreaterEqual(meta["historicalData"]["scoredMatches"], 900)
        self.assertIn("backtest", meta)
        self.assertGreaterEqual(meta["backtest"]["evaluatedMatches"], 120)
        self.assertIn("scoreModelBacktest", meta)
        self.assertGreaterEqual(meta["scoreModelBacktest"]["evaluatedMatches"], 120)
        self.assertIn("calibration", meta)
        self.assertEqual(meta["probabilityCalibrationSource"], "scoreModelBacktest")
        self.assertIn(meta["calibration"]["status"], {"active", "limited"})
        self.assertEqual(meta["probabilityCalibrationApplied"]["status"], "active")
        self.assertIn("scoringEnvironment", meta)
        self.assertEqual(meta["scoringEnvironment"]["status"], "active")
        self.assertEqual(meta["teamStrengthLayers"]["brazil"]["layers"]["recentForm"]["source"], "cc0_international_results")

    def test_model_quality_report_script_writes_auditable_report(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "model-quality-report.json"
            result = subprocess.run(
                [
                    "python3",
                    "scripts/write_model_quality_report.py",
                    "--output",
                    str(output),
                    "--max-backtest-matches",
                    "240",
                ],
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(report["historicalData"]["license"], "CC0-1.0")
            self.assertGreaterEqual(report["backtest"]["evaluatedMatches"], 200)
            self.assertIn("calibration", report)
            self.assertIn("scoreModelBacktest", report)
            self.assertEqual(report["probabilityCalibrationSource"], "scoreModelBacktest")
            self.assertEqual(report["scoringEnvironment"]["status"], "active")
            self.assertIn("teamQualitySummary", report)
            self.assertIn("brazil", report["teamQualitySummary"])


if __name__ == "__main__":
    unittest.main()
