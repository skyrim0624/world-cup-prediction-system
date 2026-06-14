import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from backend.news_feed import import_news_feed


RSS_FEED = """<?xml version="1.0" encoding="UTF-8" ?>
<rss version="2.0">
  <channel>
    <title>World Cup News</title>
    <item>
      <title>巴西边路主力恢复合练</title>
      <description>巴西边路主力恢复合练，赛前可用性提升。</description>
      <link>https://example.com/brazil-training</link>
      <pubDate>Sun, 14 Jun 2026 10:00:00 GMT</pubDate>
    </item>
    <item>
      <title>法国中卫伤情待确认</title>
      <description>法国中卫训练中单独恢复，仍待官方通报。</description>
      <link>https://example.com/france-defender</link>
      <pubDate>Sun, 14 Jun 2026 11:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>
"""


class NewsFeedImportTest(unittest.TestCase):
    def test_import_news_feed_appends_new_items_and_skips_duplicates(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "raw-news.json"
            path.write_text(
                json.dumps(
                    [
                        {
                            "id": "reuters-3a5d3e3c2a39",
                            "title": "巴西边路主力恢复合练",
                            "summary": "已有条目",
                            "source": "reuters",
                            "team": "brazil",
                            "status": "single_source",
                            "published_at": "旧时间",
                            "url": "https://example.com/brazil-training",
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            result = import_news_feed(path, RSS_FEED, source="reuters", team="france")

            rows = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(result["imported"], 1)
            self.assertEqual(result["skipped"], 1)
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[1]["title"], "法国中卫伤情待确认")
            self.assertEqual(rows[1]["team"], "france")
            self.assertEqual(rows[1]["status"], "single_source")

    def test_import_news_feed_rejects_unknown_source_when_registry_is_provided(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "raw-news.json"
            path.write_text("[]", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "未知新闻来源"):
                import_news_feed(path, RSS_FEED, source="unknown-source", team="france", known_sources={"reuters"})

            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), [])

    def test_import_news_feed_script_runs_with_temp_paths(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            feed_path = root / "feed.xml"
            raw_news_path = root / "raw-news.json"
            feed_path.write_text(RSS_FEED, encoding="utf-8")
            raw_news_path.write_text("[]", encoding="utf-8")

            result = subprocess.run(
                [
                    "python3",
                    "scripts/import_news_feed.py",
                    "--input",
                    str(feed_path),
                    "--raw-news-path",
                    str(raw_news_path),
                    "--source",
                    "reuters",
                    "--team",
                    "brazil",
                ],
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("已导入新闻 Feed", result.stdout)
            self.assertEqual(len(json.loads(raw_news_path.read_text(encoding="utf-8"))), 2)

    def test_import_news_feed_script_rejects_unknown_source(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            feed_path = root / "feed.xml"
            raw_news_path = root / "raw-news.json"
            feed_path.write_text(RSS_FEED, encoding="utf-8")
            raw_news_path.write_text("[]", encoding="utf-8")

            result = subprocess.run(
                [
                    "python3",
                    "scripts/import_news_feed.py",
                    "--input",
                    str(feed_path),
                    "--raw-news-path",
                    str(raw_news_path),
                    "--source",
                    "unknown-source",
                ],
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("未知新闻来源", result.stderr)
            self.assertEqual(json.loads(raw_news_path.read_text(encoding="utf-8")), [])


if __name__ == "__main__":
    unittest.main()
