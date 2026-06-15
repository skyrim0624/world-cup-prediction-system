import json
import tempfile
import unittest
from pathlib import Path


RSS_FEED = """<?xml version="1.0" encoding="UTF-8" ?>
<rss version="2.0">
  <channel>
    <item>
      <title>France defender injury doubt before opener</title>
      <description>France defender trained alone and remains a doubt.</description>
      <link>https://example.com/france-defender-injury</link>
      <pubDate>Mon, 15 Jun 2026 09:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>
"""

HTML_PAGE = """<!doctype html>
<html>
  <head>
    <title>Brazil forward returns to full training</title>
    <meta name="description" content="Brazil forward is available after returning to full training." />
    <link rel="canonical" href="https://www.fifa.com/brazil-forward-training" />
  </head>
  <body></body>
</html>
"""

JSON_NEWS = {
    "items": [
        {
            "headline": "France starting XI confirmed with Mbappe",
            "summary": "France starting XI is confirmed before kickoff and Mbappe starts.",
            "url": "https://www.fifa.com/france-lineup",
            "publishedAt": "2026-06-15T10:00:00Z",
        }
    ]
}


class PublicDataPipelineTest(unittest.TestCase):
    def test_pipeline_ingests_rss_html_and_json_news_sources(self):
        from backend.public_data_pipeline import load_public_data_specs, run_public_data_pipeline

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            raw_news_path = root / "raw-news.json"
            raw_news_path.write_text("[]", encoding="utf-8")
            (root / "france.xml").write_text(RSS_FEED, encoding="utf-8")
            (root / "brazil.html").write_text(HTML_PAGE, encoding="utf-8")
            (root / "fifa.json").write_text(json.dumps(JSON_NEWS), encoding="utf-8")
            config_path = root / "public-data-sources.json"
            config_path.write_text(
                json.dumps(
                    [
                        {"id": "bbc-rss", "kind": "rss", "source": "bbc", "input": "france.xml"},
                        {"id": "fifa-html", "kind": "html", "source": "fifa", "input": "brazil.html"},
                        {
                            "id": "fifa-json",
                            "kind": "json_news",
                            "source": "fifa",
                            "input": "fifa.json",
                            "itemsPath": "items",
                            "titleField": "headline",
                            "summaryField": "summary",
                            "urlField": "url",
                            "publishedField": "publishedAt",
                        },
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            report = run_public_data_pipeline(
                raw_news_path=raw_news_path,
                specs=load_public_data_specs(config_path),
                team_aliases={
                    "france": ("法国", "France", "FRA"),
                    "brazil": ("巴西", "Brazil", "BRA"),
                },
                player_aliases={"mbappe": ("Mbappe", "姆巴佩")},
                known_sources={"bbc", "fifa"},
                source_levels={"bbc": "A", "fifa": "S"},
            )

            rows = json.loads(raw_news_path.read_text(encoding="utf-8"))
            self.assertEqual(report["imported"], 3)
            self.assertEqual(report["routing"]["apply"], 3)
            self.assertEqual({row["team"] for row in rows}, {"france", "brazil"})
            self.assertTrue(any(row["kind"] == "html" for row in rows))
            self.assertTrue(any(row.get("players") == ["mbappe"] for row in rows))
            self.assertTrue(all("category" in row and "factor" in row and "confidence" in row for row in rows))

            from backend.data import load_runtime_dataset

            dataset = load_runtime_dataset(raw_news_path=raw_news_path)
            self.assertEqual(len(dataset.raw_news_items), 3)

    def test_pipeline_marks_same_event_as_multi_source(self):
        from backend.public_data_pipeline import PublicSourceSpec, run_public_data_pipeline

        second_feed = RSS_FEED.replace("https://example.com/france-defender-injury", "https://example.com/espn-france-defender")
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            raw_news_path = root / "raw-news.json"
            raw_news_path.write_text("[]", encoding="utf-8")
            bbc_path = root / "bbc.xml"
            espn_path = root / "espn.xml"
            bbc_path.write_text(RSS_FEED, encoding="utf-8")
            espn_path.write_text(second_feed, encoding="utf-8")

            report = run_public_data_pipeline(
                raw_news_path=raw_news_path,
                specs=[
                    PublicSourceSpec(id="bbc", kind="rss", source="bbc", input_path=bbc_path),
                    PublicSourceSpec(id="espn", kind="rss", source="espn", input_path=espn_path),
                ],
                team_aliases={"france": ("France", "法国", "FRA")},
                known_sources={"bbc", "espn"},
                source_levels={"bbc": "A", "espn": "A"},
            )

            rows = json.loads(raw_news_path.read_text(encoding="utf-8"))
            self.assertEqual(report["verification"]["multiSource"], 2)
            self.assertEqual({row["status"] for row in rows}, {"multi_source"})

    def test_pipeline_routes_by_source_level_and_review_status(self):
        from backend.public_data_pipeline import PublicSourceSpec, run_public_data_pipeline

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            raw_news_path = root / "raw-news.json"
            raw_news_path.write_text("[]", encoding="utf-8")
            (root / "a.xml").write_text(RSS_FEED.replace("france-defender-injury", "a.xml"), encoding="utf-8")
            (root / "c.xml").write_text(
                RSS_FEED.replace("France defender injury doubt before opener", "France heat and humidity warning")
                .replace("France defender trained alone and remains a doubt.", "France may face high humidity on match day.")
                .replace("france-defender-injury", "c.xml"),
                encoding="utf-8",
            )
            (root / "d.xml").write_text(RSS_FEED.replace("france-defender-injury", "d.xml"), encoding="utf-8")

            report = run_public_data_pipeline(
                raw_news_path=raw_news_path,
                specs=[
                    PublicSourceSpec(id="a", kind="rss", source="bbc", input_path=root / "a.xml"),
                    PublicSourceSpec(id="c", kind="rss", source="local-weather", input_path=root / "c.xml"),
                    PublicSourceSpec(id="d", kind="rss", source="social-rumor", input_path=root / "d.xml"),
                ],
                team_aliases={"france": ("France", "法国", "FRA")},
                known_sources={"bbc", "local-weather", "social-rumor"},
                source_levels={"bbc": "A", "local-weather": "C", "social-rumor": "D"},
            )

            self.assertEqual(report["routing"]["apply"], 1)
            self.assertEqual(report["routing"]["watch"], 1)
            self.assertEqual(report["routing"]["ignore"], 1)


if __name__ == "__main__":
    unittest.main()
