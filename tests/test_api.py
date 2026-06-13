import json
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

import backend.main as main_module


app = main_module.app


class PredictionApiTest(unittest.TestCase):
    def test_model_status_exposes_coverage_and_known_gaps(self):
        client = TestClient(app)
        response = client.get("/api/model-status")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["dataset"]["source"], "local-json")
        self.assertGreaterEqual(payload["dataset"]["teamCount"], 8)
        self.assertIn("knownGaps", payload)
        self.assertIn("官方 48 队名单", payload["knownGaps"][0])

    def test_match_prediction_accepts_simulation_count(self):
        client = TestClient(app)
        response = client.get("/api/match-prediction?simulations=1200")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["modelMeta"]["simulationCount"], 1200)

    def test_match_prediction_reuses_short_cache(self):
        client = TestClient(app)
        first = client.get("/api/match-prediction?simulations=1200").json()
        second = client.get("/api/match-prediction?simulations=1200").json()
        self.assertEqual(first["updatedAt"], second["updatedAt"])

    def test_events_api_exposes_review_summary(self):
        client = TestClient(app)
        response = client.get("/api/events")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["summary"]["watched"], 7)
        self.assertEqual(payload["summary"]["reviewRequired"], 1)
        self.assertGreaterEqual(len(payload["items"]), 7)
        self.assertEqual(payload["items"][0]["impact"], "全局备注")
        self.assertTrue(any(item["action"] == "watch" and item["impact"] == "待审核" for item in payload["items"]))

    def test_events_api_exposes_raw_news_ids_for_review_queue(self):
        client = TestClient(app)
        response = client.get("/api/events")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(
            any(item.get("id") == "mexico-heat-watch" and item["action"] == "watch" for item in payload["items"])
        )

    def test_review_events_api_writes_status_and_team(self):
        rows = [
            {
                "id": "weather-watch",
                "title": "小组赛天气待确认",
                "summary": "本地天气观察提示比赛日可能高温。",
                "source": "local-weather",
                "team": None,
                "status": "single_source",
                "published_at": "6 小时前",
                "url": "https://example.com/weather",
            }
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            raw_news_path = Path(temp_dir) / "raw-news.json"
            raw_news_path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
            previous_path = getattr(main_module, "review_data_path", None)
            main_module.review_data_path = raw_news_path
            try:
                client = TestClient(app)
                response = client.post(
                    "/api/events/review",
                    json={"id": "weather-watch", "status": "confirmed", "team": "brazil"},
                )
            finally:
                if previous_path is None:
                    delattr(main_module, "review_data_path")
                else:
                    main_module.review_data_path = previous_path

            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertTrue(payload["requiresSnapshotRefresh"])
            self.assertEqual(payload["item"]["status"], "confirmed")
            self.assertEqual(payload["item"]["team"], "brazil")

            updated_rows = json.loads(raw_news_path.read_text(encoding="utf-8"))
            self.assertEqual(updated_rows[0]["status"], "confirmed")
            self.assertEqual(updated_rows[0]["team"], "brazil")


if __name__ == "__main__":
    unittest.main()
