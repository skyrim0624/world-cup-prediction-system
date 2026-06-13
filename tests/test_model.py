import unittest

from backend.data import DATASET_META, EVENTS, FIXTURES, TEAM_PROFILES, THIRD_PLACE_COMBINATIONS
from backend.model import (
    ROUND_OF_16_MATCHES,
    apply_event_adjustments,
    best_third_place_teams,
    build_round_of_32_matches,
    build_score_sampler,
    build_match_prediction,
    build_standings,
    event_factor_impacts,
    group_names,
    rank_group,
    simulate_tournament,
    win_draw_loss,
)


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
        prediction = build_match_prediction(1200)
        self.assertIn("scoreOutcomes", prediction)
        self.assertIn("scenarioImpacts", prediction)
        self.assertIn("teams", prediction)
        self.assertIn("modelMeta", prediction)
        self.assertGreater(len(prediction["scoreOutcomes"]), 0)
        self.assertEqual(prediction["modelMeta"]["lockedResults"], 3)

    def test_dataset_is_loaded_from_local_json_files(self):
        self.assertEqual(DATASET_META["source"], "local-json")
        self.assertEqual(len(TEAM_PROFILES), 48)
        self.assertEqual(len(group_names(TEAM_PROFILES)), 12)
        self.assertTrue(all(len([team for team in TEAM_PROFILES.values() if team.group == group]) == 4 for group in group_names(TEAM_PROFILES)))
        self.assertGreaterEqual(len(FIXTURES), 6)
        self.assertGreaterEqual(len(EVENTS), 3)

    def test_prediction_exposes_model_transparency_meta(self):
        prediction = build_match_prediction(1200)
        self.assertEqual(prediction["modelMeta"]["dataset"]["source"], "local-json")
        self.assertEqual(prediction["modelMeta"]["events"]["watched"], 3)
        self.assertEqual(prediction["modelMeta"]["events"]["applied"], 1)
        self.assertEqual(prediction["modelMeta"]["events"]["ignored"], 1)

    def test_team_factors_use_five_product_plates(self):
        prediction = build_match_prediction(1200)
        first_team = prediction["teams"][0]
        self.assertEqual(set(first_team["factors"]), {"strength", "form", "path", "squad", "margin"})

    def test_group_ranking_only_uses_teams_from_that_group(self):
        standings = build_standings(FIXTURES)
        ranked = rank_group(standings, "E")
        self.assertEqual({TEAM_PROFILES[key].group for key in ranked}, {"E"})

    def test_best_third_place_selects_eight_teams(self):
        standings = build_standings(FIXTURES)
        third_place = best_third_place_teams(standings, TEAM_PROFILES)
        self.assertEqual(len(third_place), 8)

    def test_annex_c_third_place_table_is_loaded(self):
        self.assertEqual(len(THIRD_PLACE_COMBINATIONS), 495)
        self.assertEqual(
            THIRD_PLACE_COMBINATIONS["EFGHIJKL"],
            {"A": "E", "B": "J", "D": "I", "E": "F", "G": "H", "I": "G", "K": "L", "L": "K"},
        )

    def test_round_of_32_uses_fifa_fixed_slots(self):
        standings = build_standings(FIXTURES)
        rankings = {group: rank_group(standings, group, teams=TEAM_PROFILES) for group in group_names(TEAM_PROFILES)}
        third_place = best_third_place_teams(standings, TEAM_PROFILES, rankings=rankings)
        matches = build_round_of_32_matches(rankings, third_place, TEAM_PROFILES)
        self.assertEqual(matches[73], (rankings["A"][1], rankings["B"][1]))
        self.assertEqual(matches[74][0], rankings["E"][0])
        self.assertEqual(len(matches), 16)
        self.assertEqual(len({team for match in matches.values() for team in match}), 32)
        self.assertEqual(ROUND_OF_16_MATCHES[0], (89, 74, 77))

    def test_tournament_outputs_32_team_path_stages(self):
        teams = apply_event_adjustments()
        result = simulate_tournament(teams, simulation_count=1200)
        self.assertIn("roundOf32", result["brazil"])
        self.assertIn("roundOf16", result["brazil"])
        self.assertIn("quarterfinal", result["brazil"])

    def test_score_sampler_precomputes_cumulative_distribution(self):
        teams = apply_event_adjustments()
        sampler = build_score_sampler("brazil", "argentina", teams)
        self.assertGreater(len(sampler), 0)
        self.assertAlmostEqual(sampler[-1][0], 1.0, places=6)

    def test_events_generate_factor_impact_details(self):
        impacts = event_factor_impacts()
        self.assertLess(impacts["brazil"]["attack"], 0)
        self.assertEqual(impacts["argentina"]["squad"], 0)


if __name__ == "__main__":
    unittest.main()
