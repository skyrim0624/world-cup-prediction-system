import json
import subprocess
import tempfile
import unittest
from urllib.parse import quote
from pathlib import Path

from backend.model import reload_model_data


RSS_FEED = """<?xml version="1.0" encoding="UTF-8" ?>
<rss version="2.0">
  <channel>
    <title>World Cup Daily News</title>
    <item>
      <title>巴西边路主力恢复合练</title>
      <description>巴西边路主力恢复合练，赛前可用性提升。</description>
      <link>https://example.com/daily-brazil-training</link>
      <pubDate>Sun, 14 Jun 2026 10:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>
"""

ESPN_SCOREBOARD = {
    "events": [
        {
            "id": "760421",
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
        }
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
            "Home": {"Abbreviation": "MEX", "Score": 2, "Tactics": "4-1-2-3"},
            "Away": {"Abbreviation": "RSA", "Score": 0, "Tactics": "5-3-2"},
            "Weather": {"Humidity": "57"},
        }
    ]
}


class DailyUpdateTest(unittest.TestCase):
    def tearDown(self):
        reload_model_data()

    def test_run_daily_update_imports_feeds_and_writes_snapshot(self):
        from backend.daily_update import FeedSpec, run_daily_update

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            feed_path = root / "feed.xml"
            raw_news_path = root / "raw-news.json"
            snapshot_path = root / "latest-match-prediction.json"
            feed_path.write_text(RSS_FEED, encoding="utf-8")
            raw_news_path.write_text("[]", encoding="utf-8")

            report = run_daily_update(
                raw_news_path=raw_news_path,
                snapshot_path=snapshot_path,
                feed_specs=[FeedSpec(input_path=feed_path, source="reuters", team="brazil")],
                simulation_count=1200,
            )

            rows = json.loads(raw_news_path.read_text(encoding="utf-8"))
            snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
            self.assertEqual(report["feeds"]["imported"], 1)
            self.assertEqual(report["feeds"]["skipped"], 0)
            self.assertIn("multiSource", report["newsVerification"])
            self.assertEqual(report["snapshot"]["simulationCount"], 1200)
            self.assertEqual(report["snapshot"]["path"], str(snapshot_path))
            self.assertEqual(len(rows), 1)
            self.assertEqual(snapshot["modelMeta"]["simulationCount"], 1200)

    def test_run_daily_update_writes_latest_status_file(self):
        from backend.daily_update import FeedSpec, run_daily_update

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            feed_path = root / "feed.xml"
            raw_news_path = root / "raw-news.json"
            snapshot_path = root / "latest-match-prediction.json"
            status_path = root / "daily-update-status.json"
            feed_path.write_text(RSS_FEED, encoding="utf-8")
            raw_news_path.write_text("[]", encoding="utf-8")

            report = run_daily_update(
                raw_news_path=raw_news_path,
                snapshot_path=snapshot_path,
                feed_specs=[FeedSpec(input_path=feed_path, source="reuters", team="brazil")],
                simulation_count=1200,
                status_path=status_path,
            )

            status = json.loads(status_path.read_text(encoding="utf-8"))
            self.assertEqual(report["status"], "success")
            self.assertEqual(status["status"], "success")
            self.assertEqual(status["feeds"]["imported"], 1)
            self.assertEqual(status["snapshot"]["path"], str(snapshot_path))
            self.assertEqual(status["snapshot"]["simulationCount"], 1200)
            self.assertIn("updatedAt", status)

    def test_daily_update_script_runs_from_feed_config(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            feed_path = root / "feed.xml"
            raw_news_path = root / "raw-news.json"
            snapshot_path = root / "latest-match-prediction.json"
            config_path = root / "feed-config.json"
            feed_path.write_text(RSS_FEED, encoding="utf-8")
            raw_news_path.write_text("[]", encoding="utf-8")
            config_path.write_text(
                json.dumps(
                    [{"input": str(feed_path), "source": "reuters", "team": "brazil"}],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    "python3",
                    "scripts/run_daily_update.py",
                    "--raw-news-path",
                    str(raw_news_path),
                    "--snapshot",
                    str(snapshot_path),
                    "--feed-config",
                    str(config_path),
                    "--simulations",
                    "1200",
                ],
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("日更流程完成", result.stdout)
            self.assertTrue(snapshot_path.exists())

    def test_run_daily_update_imports_remote_feed_url_from_config(self):
        from backend.daily_update import load_feed_specs, run_daily_update

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            raw_news_path = root / "raw-news.json"
            snapshot_path = root / "latest-match-prediction.json"
            config_path = root / "feed-config.json"
            raw_news_path.write_text("[]", encoding="utf-8")
            config_path.write_text(
                json.dumps(
                    [{"url": f"data:text/xml,{quote(RSS_FEED)}", "source": "bbc", "team": "brazil"}],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            report = run_daily_update(
                raw_news_path=raw_news_path,
                snapshot_path=snapshot_path,
                feed_specs=load_feed_specs(config_path),
                simulation_count=1200,
            )

            rows = json.loads(raw_news_path.read_text(encoding="utf-8"))
            self.assertEqual(report["feeds"]["imported"], 1)
            self.assertEqual(report["feeds"]["items"][0]["url"], f"data:text/xml,{quote(RSS_FEED)}")
            self.assertEqual(rows[0]["source"], "bbc")

    def test_run_daily_update_applies_score_sources_before_snapshot(self):
        from backend.daily_update import ScoreSourceSpec, run_daily_update

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            raw_news_path = root / "raw-news.json"
            fixtures_path = root / "fixtures.json"
            snapshot_path = root / "latest-match-prediction.json"
            raw_news_path.write_text("[]", encoding="utf-8")

            fixtures = json.loads(Path("backend/data_files/fixtures.json").read_text(encoding="utf-8"))
            for fixture in fixtures:
                if fixture["home"] == "australia" and fixture["away"] == "turkiye":
                    fixture["status"] = "scheduled"
                    fixture.pop("home_score", None)
                    fixture.pop("away_score", None)
            fixtures_path.write_text(json.dumps(fixtures, ensure_ascii=False), encoding="utf-8")

            score_path = root / "scores.json"
            score_path.write_text(json.dumps(ESPN_SCOREBOARD, ensure_ascii=False), encoding="utf-8")

            report = run_daily_update(
                raw_news_path=raw_news_path,
                snapshot_path=snapshot_path,
                fixtures_path=fixtures_path,
                score_specs=[ScoreSourceSpec(input_path=score_path, source="espn", format="espn_scoreboard")],
                simulation_count=1200,
            )

            updated_fixtures = json.loads(fixtures_path.read_text(encoding="utf-8"))
            australia_fixture = next(
                fixture for fixture in updated_fixtures if fixture["home"] == "australia" and fixture["away"] == "turkiye"
            )
            snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
            self.assertEqual(report["scores"]["updated"], 1)
            self.assertEqual(australia_fixture["status"], "finished")
            self.assertEqual(australia_fixture["home_score"], 2)
            self.assertEqual(australia_fixture["away_score"], 0)
            self.assertGreaterEqual(snapshot["modelMeta"]["lockedResults"], 8)

    def test_run_daily_update_applies_fifa_official_score_source_and_reports_gaps(self):
        from backend.daily_update import ScoreSourceSpec, run_daily_update

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            raw_news_path = root / "raw-news.json"
            fixtures_path = root / "fixtures.json"
            snapshot_path = root / "latest-match-prediction.json"
            raw_news_path.write_text("[]", encoding="utf-8")

            fixtures = json.loads(Path("backend/data_files/fixtures.json").read_text(encoding="utf-8"))
            for fixture in fixtures:
                if fixture.get("match_no") == 1:
                    fixture["status"] = "scheduled"
                    fixture.pop("home_score", None)
                    fixture.pop("away_score", None)
            fixtures_path.write_text(json.dumps(fixtures, ensure_ascii=False), encoding="utf-8")

            score_path = root / "fifa-calendar.json"
            score_path.write_text(json.dumps(FIFA_CALENDAR, ensure_ascii=False), encoding="utf-8")

            report = run_daily_update(
                raw_news_path=raw_news_path,
                snapshot_path=snapshot_path,
                fixtures_path=fixtures_path,
                score_specs=[ScoreSourceSpec(input_path=score_path, source="fifa", format="fifa_calendar_matches")],
                simulation_count=1200,
            )

            updated_fixtures = json.loads(fixtures_path.read_text(encoding="utf-8"))
            mexico_fixture = next(fixture for fixture in updated_fixtures if fixture.get("match_no") == 1)
            self.assertEqual(report["scores"]["updated"], 1)
            self.assertEqual(report["scores"]["lineupsObserved"], 1)
            self.assertEqual(report["scores"]["disciplineObserved"], 0)
            self.assertEqual(report["scores"]["standingsSource"], "computed_from_official_fifa_results")
            self.assertEqual(mexico_fixture["status"], "finished")
            self.assertEqual(mexico_fixture["home_score"], 2)
            self.assertEqual(mexico_fixture["away_score"], 0)

    def test_package_daily_update_uses_real_feed_config(self):
        package = json.loads(Path("package.json").read_text(encoding="utf-8"))
        config_path = Path("backend/data_files/daily-feed-sources.json")
        config = json.loads(config_path.read_text(encoding="utf-8"))

        self.assertIn("--feed-config backend/data_files/daily-feed-sources.json", package["scripts"]["daily:update"])
        self.assertGreaterEqual(len(config), 3)
        self.assertTrue(all(row.get("url", "").startswith(("http://", "https://")) for row in config))
        self.assertTrue({"bbc", "espn", "guardian"}.issubset({row["source"] for row in config}))

    def test_default_score_source_uses_fifa_official_calendar(self):
        config = json.loads(Path("backend/data_files/score-sources.json").read_text(encoding="utf-8"))

        self.assertEqual(config[0]["source"], "fifa")
        self.assertEqual(config[0]["format"], "fifa_calendar_matches")
        self.assertIn("api.fifa.com/api/v3/calendar/matches", config[0]["url"])
        self.assertIn("IdSeason=285023", config[0]["url"])

    def test_daily_update_script_writes_status_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            raw_news_path = root / "raw-news.json"
            snapshot_path = root / "latest-match-prediction.json"
            status_path = root / "daily-update-status.json"
            raw_news_path.write_text("[]", encoding="utf-8")

            result = subprocess.run(
                [
                    "python3",
                    "scripts/run_daily_update.py",
                    "--raw-news-path",
                    str(raw_news_path),
                    "--snapshot",
                    str(snapshot_path),
                    "--status",
                    str(status_path),
                    "--simulations",
                    "1200",
                ],
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("日更流程完成", result.stdout)
            status = json.loads(status_path.read_text(encoding="utf-8"))
            self.assertEqual(status["status"], "success")
            self.assertEqual(status["snapshot"]["simulationCount"], 1200)

    def test_daily_update_script_writes_failed_status_when_feed_is_missing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            raw_news_path = root / "raw-news.json"
            snapshot_path = root / "latest-match-prediction.json"
            status_path = root / "daily-update-status.json"
            config_path = root / "feed-config.json"
            raw_news_path.write_text("[]", encoding="utf-8")
            config_path.write_text(
                json.dumps(
                    [{"input": str(root / "missing-feed.xml"), "source": "reuters", "team": "brazil"}],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    "python3",
                    "scripts/run_daily_update.py",
                    "--raw-news-path",
                    str(raw_news_path),
                    "--snapshot",
                    str(snapshot_path),
                    "--feed-config",
                    str(config_path),
                    "--status",
                    str(status_path),
                    "--simulations",
                    "1200",
                ],
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("日更流程失败", result.stderr)
            status = json.loads(status_path.read_text(encoding="utf-8"))
            self.assertEqual(status["status"], "failed")
            self.assertIn("missing-feed.xml", status["error"])
            self.assertIn("updatedAt", status)

    def test_daily_update_health_script_exits_zero_for_fresh_status(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            status_path = Path(temp_dir) / "daily-update-status.json"
            status_path.write_text(
                json.dumps({"status": "success", "updatedAt": "2026-06-14T08:00:00Z"}, ensure_ascii=False),
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    "python3",
                    "scripts/check_daily_update_health.py",
                    "--status",
                    str(status_path),
                    "--now",
                    "2026-06-14T18:00:00Z",
                ],
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("日更健康: 正常", result.stdout)

    def test_daily_update_health_script_exits_nonzero_for_stale_status(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            status_path = Path(temp_dir) / "daily-update-status.json"
            status_path.write_text(
                json.dumps({"status": "success", "updatedAt": "2026-06-13T00:00:00Z"}, ensure_ascii=False),
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    "python3",
                    "scripts/check_daily_update_health.py",
                    "--status",
                    str(status_path),
                    "--now",
                    "2026-06-14T18:00:00Z",
                ],
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("日更健康: 过期", result.stderr)


if __name__ == "__main__":
    unittest.main()
