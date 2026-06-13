import unittest

from backend.data import TEAM_PROFILES
from backend.model import apply_event_adjustments, build_match_prediction, win_draw_loss


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


if __name__ == "__main__":
    unittest.main()
