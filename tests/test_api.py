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


if __name__ == "__main__":
    unittest.main()
