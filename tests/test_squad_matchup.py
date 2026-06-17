import unittest

from backend.data import TEAM_PROFILES, Fixture
import backend.model as model_state
from backend.model import apply_event_adjustments, build_match_detail, is_fixture_upcoming, upcoming_fixture_sort_key, win_draw_loss
from backend.squad_matchup import (
    build_star_power_profile,
    build_tactical_matchup,
    apply_matchup_adjustments,
)


STAR_METRICS = {
    "brazil": {
        "starPlayers": [
            {"name": "Verified Forward", "role": "attack", "rating": 91, "availability": 0.95, "source": "authorized-test-feed"},
            {"name": "Verified Keeper", "role": "goalkeeper", "rating": 88, "availability": 1.0, "source": "authorized-test-feed"},
        ]
    }
}


class SquadMatchupTest(unittest.TestCase):
    def test_star_power_missing_data_stays_neutral(self):
        profile = build_star_power_profile("brazil", metric_rows={})

        self.assertEqual(profile["status"], "missing")
        self.assertEqual(profile["adjustments"]["attack"], 0.0)
        self.assertEqual(profile["adjustments"]["goalkeeper"], 0.0)

    def test_authorized_star_power_changes_squad_and_role_adjustments(self):
        profile = build_star_power_profile("brazil", metric_rows=STAR_METRICS)

        self.assertEqual(profile["status"], "active")
        self.assertEqual(profile["source"], "authorized_star_players")
        self.assertGreater(profile["adjustments"]["attack"], 0)
        self.assertGreater(profile["adjustments"]["goalkeeper"], 0)
        self.assertGreater(profile["adjustments"]["squad"], 0)

    def test_tactical_matchup_adjusts_single_match_teams(self):
        teams = apply_event_adjustments()
        fixture = Fixture("germany", "curacao", "小组赛", "2026-06-15T08:00:00Z", "scheduled")
        matchup = build_tactical_matchup(fixture, teams, metric_rows={})
        adjusted = apply_matchup_adjustments(teams, fixture, matchup)

        self.assertIn("home", matchup)
        self.assertIn("away", matchup)
        self.assertIn("attackVsDefense", matchup["home"]["metrics"])
        self.assertNotEqual(adjusted["germany"].attack, teams["germany"].attack)

    def test_match_detail_exposes_matchup_context(self):
        fixtures = [fixture for fixture in model_state.FIXTURES if is_fixture_upcoming(fixture)]
        fixtures.sort(key=upcoming_fixture_sort_key)
        detail = build_match_detail(fixtures[0].home, fixtures[0].away, 1200)

        self.assertIn("matchupContext", detail)
        self.assertIn("home", detail["matchupContext"])
        self.assertIn("away", detail["matchupContext"])


if __name__ == "__main__":
    unittest.main()
