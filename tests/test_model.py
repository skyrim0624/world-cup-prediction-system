import unittest

from backend.data import DATASET_META, EVENTS, FIXTURES, TEAM_PROFILES
from backend.model import apply_event_adjustments, build_match_prediction, build_standings, rank_group, win_draw_loss


class PredictionModelTest(unittest.TestCase):
    def test_win_draw_loss_sums_to_one(self):
        teams = apply_event_adjustments()
        probabilities = win_draw_loss("brazil", "argentina", teams)
        total = probabilities["home"] + probabilities["draw"] + probabilities["away"]
        self.assertAlmostEqual(total, 1.0, places=6)

    def test_low_reliability_event_does_not_change_team(self):
        teams = apply_event_adjustments()
        self.assertEqual(teams["argentina"].squad, TEAM_PROFILES["argentina"].squad)

    def test_prediction_response_has_core_fields(self):
        prediction = build_match_prediction()
        self.assertIn("scoreOutcomes", prediction)
        self.assertIn("scenarioImpacts", prediction)
        self.assertIn("teams", prediction)
        self.assertIn("modelMeta", prediction)
        self.assertGreater(len(prediction["scoreOutcomes"]), 0)
        self.assertEqual(prediction["modelMeta"]["lockedResults"], 3)

    def test_dataset_is_loaded_from_local_json_files(self):
        self.assertEqual(DATASET_META["source"], "local-json")
        self.assertGreaterEqual(len(TEAM_PROFILES), 8)
        self.assertGreaterEqual(len(FIXTURES), 6)
        self.assertGreaterEqual(len(EVENTS), 3)

    def test_prediction_exposes_model_transparency_meta(self):
        prediction = build_match_prediction()
        self.assertEqual(prediction["modelMeta"]["dataset"]["source"], "local-json")
        self.assertEqual(prediction["modelMeta"]["events"]["watched"], 3)
        self.assertEqual(prediction["modelMeta"]["events"]["applied"], 1)
        self.assertEqual(prediction["modelMeta"]["events"]["ignored"], 1)

    def test_group_ranking_only_uses_teams_from_that_group(self):
        standings = build_standings(FIXTURES)
        ranked = rank_group(standings, "E")
        self.assertEqual({TEAM_PROFILES[key].group for key in ranked}, {"E"})


if __name__ == "__main__":
    unittest.main()
