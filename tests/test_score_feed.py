import json
import tempfile
import unittest
from pathlib import Path

from backend.score_feed import apply_score_source_updates, parse_espn_scoreboard


ESPN_SCOREBOARD = {
    "events": [
        {
            "id": "760421",
            "date": "2026-06-14T04:00Z",
            "status": {"type": {"state": "post", "completed": True}},
            "competitions": [
                {
                    "status": {"type": {"state": "post", "completed": True}},
                    "competitors": [
                        {"homeAway": "home", "score": "2", "team": {"abbreviation": "AUS"}},
                        {"homeAway": "away", "score": "0", "team": {"abbreviation": "TUR"}},
                    ],
                }
            ],
        },
        {
            "id": "760422",
            "date": "2026-06-14T17:00Z",
            "status": {"type": {"state": "pre", "completed": False}},
            "competitions": [
                {
                    "status": {"type": {"state": "pre", "completed": False}},
                    "competitors": [
                        {"homeAway": "home", "score": "0", "team": {"abbreviation": "GER"}},
                        {"homeAway": "away", "score": "0", "team": {"abbreviation": "CUW"}},
                    ],
                }
            ],
        },
    ]
}


class ScoreFeedTest(unittest.TestCase):
    def test_parse_espn_scoreboard_extracts_finished_and_scheduled_scores(self):
        rows = parse_espn_scoreboard(json.dumps(ESPN_SCOREBOARD))

        self.assertEqual(rows[0]["homeCode"], "AUS")
        self.assertEqual(rows[0]["awayCode"], "TUR")
        self.assertEqual(rows[0]["homeScore"], 2)
        self.assertEqual(rows[0]["awayScore"], 0)
        self.assertEqual(rows[0]["status"], "finished")
        self.assertEqual(rows[1]["status"], "scheduled")

    def test_apply_score_source_updates_writes_finished_fixture_by_team_code(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            fixtures_path = Path(temp_dir) / "fixtures.json"
            fixtures_path.write_text(
                json.dumps(
                    [
                        {
                            "home": "australia",
                            "away": "turkiye",
                            "stage": "小组赛 D 组",
                            "kickoff": "6月14日 00:00 ET",
                            "status": "scheduled",
                        },
                        {
                            "home": "germany",
                            "away": "curacao",
                            "stage": "小组赛 E 组",
                            "kickoff": "6月14日 13:00 ET",
                            "status": "scheduled",
                        },
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            report = apply_score_source_updates(
                fixtures_path,
                [
                    {
                        "source": "espn",
                        "format": "espn_scoreboard",
                        "content": json.dumps(ESPN_SCOREBOARD),
                    }
                ],
                {"AUS": "australia", "TUR": "turkiye", "GER": "germany", "CUW": "curacao"},
            )

            fixtures = json.loads(fixtures_path.read_text(encoding="utf-8"))
            self.assertEqual(report["updated"], 1)
            self.assertEqual(report["live"], 0)
            self.assertEqual(fixtures[0]["status"], "finished")
            self.assertEqual(fixtures[0]["home_score"], 2)
            self.assertEqual(fixtures[0]["away_score"], 0)
            self.assertEqual(fixtures[1]["status"], "scheduled")


if __name__ == "__main__":
    unittest.main()
