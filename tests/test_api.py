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

    def test_admin_overview_api_returns_operational_status(self):
        rows = [
            {
                "home": "brazil",
                "away": "argentina",
                "stage": "小组赛 E 组",
                "kickoff": "6月15日 08:00",
                "status": "scheduled",
            },
            {
                "home": "spain",
                "away": "france",
                "stage": "小组赛 F 组",
                "kickoff": "进行中",
                "status": "live",
                "home_score": 1,
                "away_score": 0,
            },
            {
                "home": "england",
                "away": "portugal",
                "stage": "小组赛 B 组",
                "kickoff": "已结束",
                "status": "finished",
                "home_score": 2,
                "away_score": 2,
            },
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            fixtures_path = Path(temp_dir) / "fixtures.json"
            fixtures_path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
            previous_fixtures_path = getattr(main_module, "fixtures_data_path", None)
            main_module.fixtures_data_path = fixtures_path
            main_module.reload_model_data(main_module.review_data_path, fixtures_path)
            try:
                client = TestClient(app)
                response = client.get("/api/admin/overview")
            finally:
                if previous_fixtures_path is None:
                    delattr(main_module, "fixtures_data_path")
                else:
                    main_module.fixtures_data_path = previous_fixtures_path
                main_module.reload_model_data()

            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertEqual(payload["fixtureStatus"]["scheduled"], 70)
            self.assertEqual(payload["fixtureStatus"]["live"], 1)
            self.assertEqual(payload["fixtureStatus"]["finished"], 1)
            self.assertEqual(payload["eventSummary"]["reviewRequired"], 1)
            self.assertEqual(payload["operations"]["dailyUpdateCommand"], "npm run daily:update")
            self.assertEqual(payload["operations"]["liveScoreEndpoint"], "/api/fixtures/live")
            self.assertEqual(payload["reviewQueue"][0]["action"], "watch")

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

    def test_upcoming_matches_api_lists_scheduled_match_predictions(self):
        client = TestClient(app)
        response = client.get("/api/upcoming-matches?limit=5")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload["items"]), 5)
        first = payload["items"][0]
        self.assertEqual(first["status"], "scheduled")
        self.assertIn("homeWin", first)
        self.assertIn("draw", first)
        self.assertIn("awayWin", first)
        self.assertIn("topScore", first)
        self.assertEqual(first["homeWin"] + first["draw"] + first["awayWin"], 100)

    def test_match_detail_api_builds_prediction_for_any_scheduled_match(self):
        client = TestClient(app)
        response = client.get("/api/match-detail?home=spain&away=argentina&simulations=1200")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["homeTeam"], "spain")
        self.assertEqual(payload["awayTeam"], "argentina")
        self.assertEqual(len(payload["scoreOutcomes"]), 3)
        self.assertEqual(len(payload["scenarioImpacts"]), 3)
        self.assertEqual(payload["homeWin"] + payload["draw"] + payload["awayWin"], 100)

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
                events_response = client.get("/api/events")
            finally:
                if previous_path is None:
                    delattr(main_module, "review_data_path")
                else:
                    main_module.review_data_path = previous_path
                main_module.reload_model_data()

            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertTrue(payload["requiresSnapshotRefresh"])
            self.assertEqual(payload["item"]["status"], "confirmed")
            self.assertEqual(payload["item"]["team"], "brazil")
            reviewed_items = [item for item in events_response.json()["items"] if item.get("id") == "weather-watch"]
            self.assertEqual(len(reviewed_items), 1)
            reviewed_item = reviewed_items[0]
            self.assertEqual(reviewed_item["status"], "confirmed")
            self.assertEqual(reviewed_item["team"], "brazil")

            updated_rows = json.loads(raw_news_path.read_text(encoding="utf-8"))
            self.assertEqual(updated_rows[0]["status"], "confirmed")
            self.assertEqual(updated_rows[0]["team"], "brazil")

    def test_snapshot_rebuild_api_writes_prediction_snapshot(self):
        rows = [
            {
                "id": "weather-watch",
                "title": "自动化测试高温事件",
                "summary": "官方和本地气象均确认比赛日高温。",
                "source": "local-weather",
                "team": "brazil",
                "status": "single_source",
                "published_at": "6 小时前",
                "url": "https://example.com/weather",
            }
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            raw_news_path = Path(temp_dir) / "raw-news.json"
            raw_news_path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
            snapshot_path = Path(temp_dir) / "latest-match-prediction.json"
            previous_path = getattr(main_module, "snapshot_data_path", None)
            previous_review_path = getattr(main_module, "review_data_path", None)
            main_module.snapshot_data_path = snapshot_path
            main_module.review_data_path = raw_news_path
            try:
                client = TestClient(app)
                review_response = client.post(
                    "/api/events/review",
                    json={"id": "weather-watch", "status": "multi_source", "team": "brazil"},
                )
                self.assertEqual(review_response.status_code, 200)
                response = client.post("/api/snapshot/rebuild", json={"simulations": 1200})
            finally:
                if previous_path is None:
                    delattr(main_module, "snapshot_data_path")
                else:
                    main_module.snapshot_data_path = previous_path
                if previous_review_path is None:
                    delattr(main_module, "review_data_path")
                else:
                    main_module.review_data_path = previous_review_path
                main_module.reload_model_data()

            self.assertEqual(response.status_code, 200)
            self.assertTrue(snapshot_path.exists())
            payload = response.json()
            self.assertEqual(payload["snapshotMeta"]["path"], str(snapshot_path))
            self.assertEqual(payload["modelMeta"]["simulationCount"], 1200)
            self.assertTrue(
                any(item["title"] == "自动化测试高温事件" and item["impact"] == "轻微修正" for item in payload["newsItems"])
            )

    def test_raw_news_api_appends_item_and_refreshes_event_queue(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            raw_news_path = Path(temp_dir) / "raw-news.json"
            raw_news_path.write_text("[]", encoding="utf-8")
            previous_review_path = getattr(main_module, "review_data_path", None)
            main_module.review_data_path = raw_news_path
            try:
                client = TestClient(app)
                response = client.post(
                    "/api/raw-news",
                    json={
                        "id": "manual-brazil-lineup",
                        "title": "巴西赛前首发待确认",
                        "summary": "跟队消息称巴西边路首发仍有调整可能。",
                        "source": "reuters",
                        "team": "brazil",
                        "status": "single_source",
                        "publishedAt": "刚刚",
                        "url": "https://example.com/manual-brazil-lineup",
                    },
                )
                events_response = client.get("/api/events")
            finally:
                if previous_review_path is None:
                    delattr(main_module, "review_data_path")
                else:
                    main_module.review_data_path = previous_review_path
                main_module.reload_model_data()

            self.assertEqual(response.status_code, 200)
            rows = json.loads(raw_news_path.read_text(encoding="utf-8"))
            self.assertEqual(rows[0]["id"], "manual-brazil-lineup")
            self.assertEqual(rows[0]["published_at"], "刚刚")
            self.assertTrue(any(item["id"] == "manual-brazil-lineup" for item in events_response.json()["items"]))

    def test_fixture_result_api_locks_finished_match_and_refreshes_model_status(self):
        rows = [
            {
                "home": "brazil",
                "away": "argentina",
                "stage": "小组赛 E 组",
                "kickoff": "6月15日 08:00",
                "status": "scheduled",
            }
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            fixtures_path = Path(temp_dir) / "fixtures.json"
            fixtures_path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
            previous_fixtures_path = getattr(main_module, "fixtures_data_path", None)
            main_module.fixtures_data_path = fixtures_path
            try:
                client = TestClient(app)
                response = client.post(
                    "/api/fixtures/result",
                    json={"home": "brazil", "away": "argentina", "homeScore": 2, "awayScore": 1},
                )
                status_response = client.get("/api/model-status")
            finally:
                if previous_fixtures_path is None:
                    delattr(main_module, "fixtures_data_path")
                else:
                    main_module.fixtures_data_path = previous_fixtures_path
                main_module.reload_model_data()

            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertEqual(payload["fixture"]["status"], "finished")
            self.assertEqual(payload["fixture"]["home_score"], 2)
            updated_rows = json.loads(fixtures_path.read_text(encoding="utf-8"))
            self.assertEqual(updated_rows[0]["status"], "finished")
            self.assertEqual(status_response.json()["lockedResults"], 1)

    def test_fixture_live_api_marks_in_progress_match_and_refreshes_model_status(self):
        rows = [
            {
                "home": "brazil",
                "away": "argentina",
                "stage": "小组赛 E 组",
                "kickoff": "6月15日 08:00",
                "status": "scheduled",
            }
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            fixtures_path = Path(temp_dir) / "fixtures.json"
            fixtures_path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
            previous_fixtures_path = getattr(main_module, "fixtures_data_path", None)
            main_module.fixtures_data_path = fixtures_path
            try:
                client = TestClient(app)
                response = client.post(
                    "/api/fixtures/live",
                    json={"home": "brazil", "away": "argentina", "homeScore": 1, "awayScore": 0},
                )
                status_response = client.get("/api/model-status")
            finally:
                if previous_fixtures_path is None:
                    delattr(main_module, "fixtures_data_path")
                else:
                    main_module.fixtures_data_path = previous_fixtures_path
                main_module.reload_model_data()

            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertEqual(payload["fixture"]["status"], "live")
            self.assertEqual(payload["fixture"]["home_score"], 1)
            updated_rows = json.loads(fixtures_path.read_text(encoding="utf-8"))
            self.assertEqual(updated_rows[0]["status"], "live")
            self.assertEqual(status_response.json()["liveMatches"], 1)


if __name__ == "__main__":
    unittest.main()
