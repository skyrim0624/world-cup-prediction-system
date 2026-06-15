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

PROXY_SIGNAL_NEWS = {
    "items": [
        {
            "headline": "Brazil expected goals and shot quality surge",
            "summary": "Brazil created strong xG, more big chances and better shot quality in recent matches.",
            "url": "https://example.com/brazil-xg",
            "publishedAt": "2026-06-15T11:00:00Z",
        },
        {
            "headline": "France xGA concern after conceding big chances",
            "summary": "France allowed higher xGA and big chances against elite opponents.",
            "url": "https://example.com/france-xga",
            "publishedAt": "2026-06-15T11:10:00Z",
        },
        {
            "headline": "England market odds shorten after lineup news",
            "summary": "England have shortened in the public market after positive availability reports.",
            "url": "https://example.com/england-market",
            "publishedAt": "2026-06-15T11:20:00Z",
        },
        {
            "headline": "France forward Mbappe injury doubt before opener",
            "summary": "Mbappe remains a doubt after training separately from the squad.",
            "url": "https://example.com/mbappe-status",
            "publishedAt": "2026-06-15T11:30:00Z",
        },
    ]
}

HTML_INDEX_PAGE = """<!doctype html>
<html>
  <body>
    <a href="/en/news/brazil-expected-goals-shot-quality">Brazil expected goals and shot quality surge</a>
    <a href="https://www.fifa.com/en/news/france-lineup">France starting XI confirmed</a>
    <a href="/en/about-fifa">About FIFA</a>
  </body>
</html>
"""


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

    def test_pipeline_classifies_xg_market_and_player_proxy_signals(self):
        from backend.public_data_pipeline import PublicSourceSpec, run_public_data_pipeline

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            raw_news_path = root / "raw-news.json"
            raw_news_path.write_text("[]", encoding="utf-8")
            proxy_path = root / "proxy.json"
            proxy_path.write_text(json.dumps(PROXY_SIGNAL_NEWS), encoding="utf-8")

            report = run_public_data_pipeline(
                raw_news_path=raw_news_path,
                specs=[
                    PublicSourceSpec(
                        id="trusted-proxy-json",
                        kind="json_news",
                        source="ap",
                        input_path=proxy_path,
                        title_field="headline",
                        summary_field="summary",
                        url_field="url",
                        published_field="publishedAt",
                    )
                ],
                team_aliases={
                    "brazil": ("Brazil", "巴西", "BRA"),
                    "france": ("France", "法国", "FRA"),
                    "england": ("England", "英格兰", "ENG"),
                },
                player_aliases={"mbappe": ("Mbappe", "Kylian Mbappe", "姆巴佩")},
                known_sources={"ap"},
                source_levels={"ap": "A"},
            )

            rows = json.loads(raw_news_path.read_text(encoding="utf-8"))
            by_url = {row["url"]: row for row in rows}
            self.assertEqual(report["imported"], 4)
            self.assertEqual(by_url["https://example.com/brazil-xg"]["category"], "xg_proxy")
            self.assertEqual(by_url["https://example.com/brazil-xg"]["factor"], "attack")
            self.assertEqual(by_url["https://example.com/brazil-xg"]["direction"], 1)
            self.assertEqual(by_url["https://example.com/france-xga"]["category"], "xg_proxy")
            self.assertEqual(by_url["https://example.com/france-xga"]["factor"], "defense")
            self.assertEqual(by_url["https://example.com/france-xga"]["direction"], -1)
            self.assertEqual(by_url["https://example.com/england-market"]["category"], "market_proxy")
            self.assertEqual(by_url["https://example.com/england-market"]["factor"], "path")
            self.assertEqual(by_url["https://example.com/england-market"]["direction"], 1)
            self.assertEqual(by_url["https://example.com/mbappe-status"]["category"], "player_status")
            self.assertEqual(by_url["https://example.com/mbappe-status"]["players"], ["mbappe"])

    def test_html_index_source_extracts_article_links(self):
        from backend.public_data_pipeline import PublicSourceSpec, parse_public_source

        spec = PublicSourceSpec(
            id="fifa-news-index",
            kind="html_index",
            source="fifa",
            url="https://www.fifa.com/en/news",
        )

        rows = parse_public_source(HTML_INDEX_PAGE, spec)

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["kind"], "html_index")
        self.assertEqual(rows[0]["url"], "https://www.fifa.com/en/news/brazil-expected-goals-shot-quality")
        self.assertEqual(rows[0]["category"], "xg_proxy")
        self.assertEqual(rows[0]["factor"], "attack")

    def test_pipeline_continues_when_source_fetch_or_parse_fails(self):
        from backend.public_data_pipeline import PublicSourceSpec, run_public_data_pipeline

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            raw_news_path = root / "raw-news.json"
            raw_news_path.write_text("[]", encoding="utf-8")
            valid_path = root / "valid.xml"
            valid_path.write_text(RSS_FEED, encoding="utf-8")

            report = run_public_data_pipeline(
                raw_news_path=raw_news_path,
                specs=[
                    PublicSourceSpec(id="missing", kind="rss", source="bbc", input_path=root / "missing.xml"),
                    PublicSourceSpec(id="valid", kind="rss", source="bbc", input_path=valid_path),
                ],
                team_aliases={"france": ("France", "法国", "FRA")},
                known_sources={"bbc"},
                source_levels={"bbc": "A"},
            )

            rows = json.loads(raw_news_path.read_text(encoding="utf-8"))
            self.assertEqual(report["status"], "partial_success")
            self.assertEqual(report["imported"], 1)
            self.assertEqual(len(rows), 1)
            self.assertEqual(report["sources"][0]["status"], "failed")
            self.assertIn("missing.xml", report["sources"][0]["error"])
            self.assertEqual(report["sources"][1]["status"], "success")

    def test_player_alias_loader_normalizes_alias_lists(self):
        from backend.public_data_pipeline import load_player_aliases

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "player-aliases.json"
            path.write_text(
                json.dumps({"kylian-mbappe": ["Kylian Mbappé", "Mbappe", "姆巴佩"]}, ensure_ascii=False),
                encoding="utf-8",
            )

            aliases = load_player_aliases(path)

            self.assertEqual(aliases["kylian-mbappe"], ("Kylian Mbappé", "Mbappe", "姆巴佩"))


if __name__ == "__main__":
    unittest.main()
