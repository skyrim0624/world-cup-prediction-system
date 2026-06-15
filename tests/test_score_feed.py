import json
import tempfile
import unittest
from pathlib import Path

from backend.score_feed import apply_score_source_updates, parse_espn_scoreboard, parse_fifa_calendar_matches


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

FIFA_CALENDAR = {
    "Results": [
        {
            "IdMatch": 400021443,
            "MatchNumber": 1,
            "Date": "2026-06-11T19:00:00Z",
            "HomeTeamScore": 2,
            "AwayTeamScore": 0,
            "MatchStatus": 0,
            "ResultType": 1,
            "MatchTime": "98'",
            "Home": {"Abbreviation": "MEX", "Score": 2, "Tactics": "4-1-2-3"},
            "Away": {"Abbreviation": "RSA", "Score": 0, "Tactics": "5-3-2"},
            "Stadium": {"Name": [{"Description": "Estadio Azteca"}]},
            "Weather": {"Humidity": "57"},
        },
        {
            "IdMatch": 400021467,
            "MatchNumber": 9,
            "Date": "2026-06-14T23:00:00Z",
            "HomeTeamScore": None,
            "AwayTeamScore": None,
            "MatchStatus": 1,
            "ResultType": 0,
            "Home": {"Abbreviation": "CIV", "Score": None},
            "Away": {"Abbreviation": "ECU", "Score": None},
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

    def test_parse_fifa_calendar_matches_extracts_official_result_and_metadata(self):
        rows = parse_fifa_calendar_matches(json.dumps(FIFA_CALENDAR))

        self.assertEqual(rows[0]["sourceEventId"], "400021443")
        self.assertEqual(rows[0]["matchNumber"], 1)
        self.assertEqual(rows[0]["homeCode"], "MEX")
        self.assertEqual(rows[0]["awayCode"], "RSA")
        self.assertEqual(rows[0]["homeScore"], 2)
        self.assertEqual(rows[0]["awayScore"], 0)
        self.assertEqual(rows[0]["status"], "finished")
        self.assertTrue(rows[0]["metadata"]["lineupObserved"])
        self.assertTrue(rows[0]["metadata"]["weatherObserved"])
        self.assertTrue(rows[0]["metadata"]["stadiumObserved"])
        self.assertFalse(rows[0]["metadata"]["disciplineObserved"])
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

    def test_apply_score_source_updates_prefers_fifa_match_number_and_reports_metadata(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            fixtures_path = Path(temp_dir) / "fixtures.json"
            fixtures_path.write_text(
                json.dumps(
                    [
                        {
                            "home": "mexico",
                            "away": "south-africa",
                            "stage": "小组赛 A 组",
                            "kickoff": "2026-06-11T19:00:00Z",
                            "status": "scheduled",
                            "match_no": 1,
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            report = apply_score_source_updates(
                fixtures_path,
                [
                    {
                        "source": "fifa",
                        "format": "fifa_calendar_matches",
                        "content": json.dumps(FIFA_CALENDAR),
                    }
                ],
                {"MEX": "mexico", "RSA": "south-africa", "CIV": "cote-divoire", "ECU": "ecuador"},
            )

            fixtures = json.loads(fixtures_path.read_text(encoding="utf-8"))
            item = report["items"][0]
            self.assertEqual(report["updated"], 1)
            self.assertEqual(report["lineupsObserved"], 1)
            self.assertEqual(report["weatherObserved"], 1)
            self.assertEqual(report["stadiumsObserved"], 1)
            self.assertEqual(report["disciplineObserved"], 0)
            self.assertEqual(item["parsed"], 2)
            self.assertEqual(item["lineupsObserved"], 1)
            self.assertEqual(fixtures[0]["status"], "finished")
            self.assertEqual(fixtures[0]["home_score"], 2)
            self.assertEqual(fixtures[0]["away_score"], 0)

    def test_apply_score_source_updates_never_downgrades_finished_fixture(self):
        live_payload = {
            "events": [
                {
                    "id": "760421",
                    "status": {"type": {"state": "in", "completed": False}},
                    "competitions": [
                        {
                            "status": {"type": {"state": "in", "completed": False}},
                            "competitors": [
                                {"homeAway": "home", "score": "1", "team": {"abbreviation": "AUS"}},
                                {"homeAway": "away", "score": "1", "team": {"abbreviation": "TUR"}},
                            ],
                        }
                    ],
                }
            ]
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            fixtures_path = Path(temp_dir) / "fixtures.json"
            fixtures_path.write_text(
                json.dumps(
                    [
                        {
                            "home": "australia",
                            "away": "turkiye",
                            "stage": "小组赛 D 组",
                            "kickoff": "2026-06-14T04:00:00Z",
                            "status": "finished",
                            "home_score": 2,
                            "away_score": 0,
                            "match_no": 24,
                        }
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
                        "content": json.dumps(live_payload),
                    }
                ],
                {"AUS": "australia", "TUR": "turkiye"},
            )

            fixtures = json.loads(fixtures_path.read_text(encoding="utf-8"))
            self.assertEqual(report["updated"], 0)
            self.assertEqual(report["staleSkipped"], 1)
            self.assertEqual(fixtures[0]["status"], "finished")
            self.assertEqual(fixtures[0]["home_score"], 2)
            self.assertEqual(fixtures[0]["away_score"], 0)


if __name__ == "__main__":
    unittest.main()
