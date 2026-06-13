import json
import subprocess
import tempfile
import unittest
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


if __name__ == "__main__":
    unittest.main()
