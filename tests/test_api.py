import unittest

from fastapi.testclient import TestClient

from backend.main import app


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


if __name__ == "__main__":
    unittest.main()
