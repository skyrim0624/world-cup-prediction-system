import unittest

from backend.data import FIXTURES, TEAM_PROFILES
from backend.model import advanced_metric_impacts, build_match_prediction
from backend.team_strength import (
    PROFESSIONAL_GAP_IDS,
    TEAM_STRENGTH_LAYER_IDS,
    build_team_strength_profile,
    professional_gap_coverage,
)


AUTHORIZED_METRICS = {
    "brazil": {
        "source": "authorized-test-feed",
        "elitePerformance": {
            "top20XgDiff": 0.72,
            "top20ResultIndex": 0.68,
            "daysSinceTop20Win": 120,
        },
        "squadContinuity": {
            "lineupContinuity": 0.84,
            "projectedXiStrength": 87,
            "injuryReplacementDropoff": 0.04,
        },
        "attackQuality": {
            "npXgFor": 1.92,
            "shotQuality": 0.15,
            "boxEntries": 31,
            "transitionXg": 0.42,
            "setPieceXgFor": 0.28,
        },
        "defenseQuality": {
            "npXgAgainst": 0.76,
            "bigChancesAllowed": 0.7,
            "transitionXgAgainst": 0.14,
            "setPieceXgAgainst": 0.12,
        },
        "goalkeeperQuality": {
            "postShotXgMinusGoalsAllowed": 0.24,
            "claimCrossRate": 0.11,
            "sweeperActions": 1.4,
        },
        "tacticalProfile": {
            "pressResistance": 0.74,
            "pressingIntensity": 0.66,
            "setPieceMismatch": 0.22,
        },
    }
}


class TeamStrengthLayerTest(unittest.TestCase):
    def test_team_strength_profile_exposes_eight_layers_without_fabricating_missing_data(self):
        profile = build_team_strength_profile("brazil", TEAM_PROFILES, FIXTURES, metric_rows={})
        layers = profile["layers"]

        self.assertEqual(list(layers), TEAM_STRENGTH_LAYER_IDS)
        self.assertEqual(layers["baseStrength"]["status"], "active")
        self.assertIn("historicalElo", layers["baseStrength"]["metrics"])
        self.assertEqual(layers["baseStrength"]["source"], "teams_json_and_cc0_history_elo")
        self.assertTrue(any(value != 0.0 for value in layers["baseStrength"]["adjustments"].values()))
        self.assertIn(layers["recentForm"]["status"], {"active", "neutral"})
        self.assertEqual(layers["attackQuality"]["status"], "missing")
        self.assertEqual(layers["attackQuality"]["source"], "missing_authorized_data")
        self.assertEqual(layers["attackQuality"]["adjustments"]["attack"], 0.0)
        self.assertEqual(layers["squadContinuity"]["adjustments"]["squad"], 0.0)

    def test_authorized_advanced_metrics_change_model_adjustments(self):
        neutral = advanced_metric_impacts(TEAM_PROFILES, metric_rows={})
        enriched = advanced_metric_impacts(TEAM_PROFILES, metric_rows=AUTHORIZED_METRICS)

        self.assertGreater(enriched["brazil"]["attack"], neutral["brazil"]["attack"])
        self.assertGreater(enriched["brazil"]["defense"], neutral["brazil"]["defense"])
        self.assertGreater(enriched["brazil"]["goalkeeper"], neutral["brazil"]["goalkeeper"])
        self.assertGreater(enriched["brazil"]["squad"], neutral["brazil"]["squad"])
        self.assertGreater(enriched["brazil"]["overall"], neutral["brazil"]["overall"])

    def test_professional_gap_coverage_lists_nine_gaps_and_neutral_missing_layers(self):
        coverage = professional_gap_coverage(metric_rows={})

        self.assertEqual([item["id"] for item in coverage], PROFESSIONAL_GAP_IDS)
        self.assertTrue(all(item["status"] in {"active", "missing"} for item in coverage))
        missing = [item for item in coverage if item["status"] == "missing"]
        self.assertGreaterEqual(len(missing), 6)
        self.assertTrue(all(item["modelEffect"] == "neutral" for item in missing))

    def test_prediction_meta_exposes_strength_layers_and_professional_gap_status(self):
        prediction = build_match_prediction(1200)
        meta = prediction["modelMeta"]

        self.assertEqual(meta["advancedMetrics"]["source"], "verified_layered_inputs")
        self.assertIn("teamStrengthLayers", meta)
        self.assertIn("professionalGapCoverage", meta)
        self.assertEqual(list(meta["teamStrengthLayers"]["brazil"]["layers"]), TEAM_STRENGTH_LAYER_IDS)
        self.assertEqual([item["id"] for item in meta["professionalGapCoverage"]], PROFESSIONAL_GAP_IDS)


if __name__ == "__main__":
    unittest.main()
