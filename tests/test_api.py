import json
import os
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

import backend.main as main_module
from test_data_import import make_team


app = main_module.app


def make_compatible_import_payload() -> dict[str, object]:
    groups = tuple("ABCDEFGHIJKL")
    fixed_teams = {
        "E": [
            {"key": "brazil", "name": "巴西", "code": "BRA"},
            {"key": "argentina", "name": "阿根廷", "code": "ARG"},
            {"key": "spain", "name": "西班牙", "code": "ESP"},
            {"key": "france", "name": "法国", "code": "FRA"},
        ],
        "F": [
            {"key": "england", "name": "英格兰", "code": "ENG"},
            {"key": "portugal", "name": "葡萄牙", "code": "POR"},
            {"key": "germany", "name": "德国", "code": "GER"},
            {"key": "netherlands", "name": "荷兰", "code": "NED"},
        ],
    }
    teams = []
    for group in groups:
        if group in fixed_teams:
            for index, row in enumerate(fixed_teams[group], start=1):
                teams.append(
                    {
                        **row,
                        "group": group,
                        "elo": 1800 - index,
                        "attack": 80,
                        "defense": 80,
                        "goalkeeper": 80,
                        "path": 70,
                        "squad": 80,
                    }
                )
            continue
        for slot in range(1, 5):
            team = make_team(group, slot)
            team["key"] = f"official-{group.lower()}-{slot}"
            team["code"] = f"{group}{slot}"
            teams.append(team)

    fixtures = []
    for group in groups:
        group_keys = [team["key"] for team in teams if team["group"] == group]
        for index, home in enumerate(group_keys):
            for away in group_keys[index + 1 :]:
                fixtures.append(
                    {
                        "home": home,
                        "away": away,
                        "stage": f"小组赛 {group} 组",
                        "kickoff": "待定",
                        "status": "scheduled",
                    }
                )
    return {
        "source": "fifa-official-test",
        "retrievedAt": "2026-06-14T00:00:00Z",
        "teams": teams,
        "fixtures": fixtures,
    }


class PredictionApiTest(unittest.TestCase):
    def test_model_status_exposes_coverage_and_known_gaps(self):
        client = TestClient(app)
        response = client.get("/api/model-status")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["dataset"]["source"], "fifa-official-match-schedule-2026")
        self.assertEqual(payload["dataset"]["teamCount"], 48)
        self.assertIn("knownGaps", payload)
        self.assertIn("小组赛真实赛程", payload["knownGaps"][0])
        self.assertIn("真实新闻 Feed 配置已接入", payload["knownGaps"][1])
        self.assertIn("支付已有客户接口框架", payload["knownGaps"][2])

    def test_local_vite_fallback_port_is_allowed_by_cors(self):
        client = TestClient(app)

        response = client.options(
            "/api/health",
            headers={
                "Origin": "http://127.0.0.1:5175",
                "Access-Control-Request-Method": "GET",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["access-control-allow-origin"], "http://127.0.0.1:5175")

    def test_model_status_exposes_tournament_provenance(self):
        payload = make_compatible_import_payload()
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)
            teams_path = data_dir / "teams.json"
            fixtures_path = data_dir / "fixtures.json"
            provenance_path = data_dir / "tournament-provenance.json"
            teams_path.write_text(json.dumps(payload["teams"], ensure_ascii=False), encoding="utf-8")
            fixtures_path.write_text(json.dumps(payload["fixtures"], ensure_ascii=False), encoding="utf-8")
            provenance_path.write_text(
                json.dumps(
                    {
                        "source": "fifa-official-test",
                        "retrievedAt": "2026-06-14T00:00:00Z",
                        "sourceUrl": "https://www.fifa.com/en/tournaments/mens/worldcup/canadamexicousa2026",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            previous_fixtures_path = getattr(main_module, "fixtures_data_path", None)
            main_module.fixtures_data_path = fixtures_path
            try:
                main_module.reload_model_data(main_module.review_data_path, fixtures_path, teams_path)
                client = TestClient(app)
                response = client.get("/api/model-status")
            finally:
                if previous_fixtures_path is None:
                    delattr(main_module, "fixtures_data_path")
                else:
                    main_module.fixtures_data_path = previous_fixtures_path
                main_module.reload_model_data()

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["dataset"]["tournamentSource"]["source"], "fifa-official-test")
            self.assertEqual(response.json()["dataset"]["tournamentSource"]["sourceUrl"], "https://www.fifa.com/en/tournaments/mens/worldcup/canadamexicousa2026")

    def test_access_options_expose_paid_unlock_boundary(self):
        client = TestClient(app)
        response = client.get("/api/access-options")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertFalse(payload["paymentConfigured"])
        self.assertEqual([product["key"] for product in payload["products"]], ["single_match", "tournament_pass", "match_pack"])
        self.assertTrue(all(product["status"] == "payment_pending" for product in payload["products"]))
        self.assertIn("概率分析", payload["disclaimer"])

    def test_access_policy_exposes_content_gates(self):
        client = TestClient(app)
        response = client.get("/api/access-policy")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertFalse(payload["paymentConfigured"])
        self.assertEqual(payload["content"][0]["contentKey"], "match_prediction")
        self.assertIn("single_match", payload["content"][0]["requiredProducts"])
        self.assertEqual(payload["content"][1]["contentKey"], "tournament_probabilities")
        self.assertEqual(payload["content"][1]["requiredProducts"], ["tournament_pass"])

    def test_admin_overview_api_returns_operational_status(self):
        rows = [
            {
                "home": "germany",
                "away": "curacao",
                "stage": "小组赛 E 组",
                "kickoff": "6月15日 08:00",
                "status": "scheduled",
            },
            {
                "home": "cote-divoire",
                "away": "ecuador",
                "stage": "小组赛 E 组",
                "kickoff": "进行中",
                "status": "live",
                "home_score": 1,
                "away_score": 0,
            },
            {
                "home": "mexico",
                "away": "south-africa",
                "stage": "小组赛 A 组",
                "kickoff": "已结束",
                "status": "finished",
                "home_score": 2,
                "away_score": 0,
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

    def test_admin_overview_api_returns_daily_update_status(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            status_path = Path(temp_dir) / "daily-update-status.json"
            status_path.write_text(
                json.dumps(
                    {
                        "status": "success",
                        "updatedAt": "2026-06-14T08:00:00Z",
                        "feeds": {"imported": 2, "skipped": 1, "items": []},
                        "snapshot": {
                            "path": "backend/data_files/latest-match-prediction.json",
                            "simulationCount": 50000,
                            "lockedResults": 4,
                            "liveMatches": 1,
                            "events": {"applied": 5, "watched": 2, "ignored": 1, "reviewRequired": 1},
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            previous_status_path = getattr(main_module, "daily_status_path", None)
            main_module.daily_status_path = status_path
            try:
                client = TestClient(app)
                response = client.get("/api/admin/overview")
            finally:
                if previous_status_path is None:
                    delattr(main_module, "daily_status_path")
                else:
                    main_module.daily_status_path = previous_status_path

            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertEqual(payload["dailyUpdateStatus"]["status"], "success")
            self.assertEqual(payload["dailyUpdateStatus"]["feeds"]["imported"], 2)
            self.assertEqual(payload["dailyUpdateStatus"]["snapshot"]["liveMatches"], 1)

    def test_admin_overview_api_returns_tournament_backups(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            backup_root = Path(temp_dir) / "backups"
            backup_dir = backup_root / "20260614T080000000000Z"
            backup_dir.mkdir(parents=True)
            (backup_dir / "teams.json").write_text("[]", encoding="utf-8")
            (backup_dir / "fixtures.json").write_text("[]", encoding="utf-8")
            previous_backup_dir = getattr(main_module, "tournament_backup_dir", None)
            main_module.tournament_backup_dir = backup_root
            try:
                client = TestClient(app)
                response = client.get("/api/admin/overview")
            finally:
                if previous_backup_dir is None:
                    delattr(main_module, "tournament_backup_dir")
                else:
                    main_module.tournament_backup_dir = previous_backup_dir

            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertEqual(payload["tournamentBackups"][0]["backupId"], "20260614T080000000000Z")
            self.assertTrue(payload["tournamentBackups"][0]["isComplete"])

    def test_admin_write_apis_require_token_when_configured(self):
        previous_token = os.environ.get("WORLD_CUP_ADMIN_TOKEN")
        os.environ["WORLD_CUP_ADMIN_TOKEN"] = "secret-token"
        try:
            client = TestClient(app)
            response = client.post("/api/snapshot/rebuild", json={"simulations": 1200})
        finally:
            if previous_token is None:
                os.environ.pop("WORLD_CUP_ADMIN_TOKEN", None)
            else:
                os.environ["WORLD_CUP_ADMIN_TOKEN"] = previous_token

        self.assertEqual(response.status_code, 401)

    def test_raw_news_write_appends_admin_audit_when_authorized(self):
        previous_token = os.environ.get("WORLD_CUP_ADMIN_TOKEN")
        os.environ["WORLD_CUP_ADMIN_TOKEN"] = "secret-token"
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            raw_news_path = root / "raw-news.json"
            audit_path = root / "admin-audit.jsonl"
            raw_news_path.write_text("[]", encoding="utf-8")
            previous_review_path = getattr(main_module, "review_data_path", None)
            previous_audit_path = getattr(main_module, "audit_log_path", None)
            main_module.review_data_path = raw_news_path
            main_module.audit_log_path = audit_path
            try:
                client = TestClient(app)
                response = client.post(
                    "/api/raw-news",
                    headers={"X-Admin-Token": "secret-token"},
                    json={
                        "id": "manual-admin-audit",
                        "title": "巴西赛前训练消息",
                        "summary": "跟队记者称巴西主力边路恢复合练。",
                        "source": "reuters",
                        "team": "brazil",
                        "status": "single_source",
                        "publishedAt": "刚刚",
                        "url": "https://example.com/admin-audit",
                    },
                )
            finally:
                if previous_review_path is None:
                    delattr(main_module, "review_data_path")
                else:
                    main_module.review_data_path = previous_review_path
                if previous_audit_path is None:
                    delattr(main_module, "audit_log_path")
                else:
                    main_module.audit_log_path = previous_audit_path
                main_module.reload_model_data()
                if previous_token is None:
                    os.environ.pop("WORLD_CUP_ADMIN_TOKEN", None)
                else:
                    os.environ["WORLD_CUP_ADMIN_TOKEN"] = previous_token

            self.assertEqual(response.status_code, 200, response.text)
            audit_rows = [json.loads(line) for line in audit_path.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(audit_rows[0]["action"], "raw-news:create")
            self.assertEqual(audit_rows[0]["targetId"], "manual-admin-audit")

    def test_admin_tournament_import_writes_files_reload_model_and_audit(self):
        previous_token = os.environ.get("WORLD_CUP_ADMIN_TOKEN")
        os.environ["WORLD_CUP_ADMIN_TOKEN"] = "secret-token"
        payload = make_compatible_import_payload()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_dir = root / "data"
            backup_dir = root / "backups"
            audit_path = root / "admin-audit.jsonl"
            data_dir.mkdir()
            (data_dir / "teams.json").write_text("[]", encoding="utf-8")
            (data_dir / "fixtures.json").write_text("[]", encoding="utf-8")
            previous_data_dir = getattr(main_module, "runtime_data_dir", None)
            previous_backup_dir = getattr(main_module, "tournament_backup_dir", None)
            previous_audit_path = getattr(main_module, "audit_log_path", None)
            previous_fixtures_path = getattr(main_module, "fixtures_data_path", None)
            main_module.runtime_data_dir = data_dir
            main_module.tournament_backup_dir = backup_dir
            main_module.audit_log_path = audit_path
            main_module.fixtures_data_path = data_dir / "fixtures.json"
            try:
                client = TestClient(app)
                response = client.post(
                    "/api/admin/tournament-data/import",
                    headers={"X-Admin-Token": "secret-token"},
                    json=payload,
                )
                status_response = client.get("/api/model-status")
            finally:
                if previous_data_dir is None:
                    delattr(main_module, "runtime_data_dir")
                else:
                    main_module.runtime_data_dir = previous_data_dir
                if previous_backup_dir is None:
                    delattr(main_module, "tournament_backup_dir")
                else:
                    main_module.tournament_backup_dir = previous_backup_dir
                if previous_audit_path is None:
                    delattr(main_module, "audit_log_path")
                else:
                    main_module.audit_log_path = previous_audit_path
                if previous_fixtures_path is None:
                    delattr(main_module, "fixtures_data_path")
                else:
                    main_module.fixtures_data_path = previous_fixtures_path
                main_module.reload_model_data()
                if previous_token is None:
                    os.environ.pop("WORLD_CUP_ADMIN_TOKEN", None)
                else:
                    os.environ["WORLD_CUP_ADMIN_TOKEN"] = previous_token

            self.assertEqual(response.status_code, 200, response.text)
            result = response.json()
            self.assertEqual(result["teamCount"], 48)
            self.assertEqual(result["fixtureCount"], 72)
            self.assertEqual(status_response.json()["dataset"]["placeholderSlots"], 0)
            self.assertEqual(len(json.loads((data_dir / "teams.json").read_text(encoding="utf-8"))), 48)
            self.assertTrue(Path(result["backupDir"]).exists())
            audit_rows = [json.loads(line) for line in audit_path.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(audit_rows[0]["action"], "tournament-data:import")
            self.assertEqual(audit_rows[0]["targetId"], "fifa-official-test")

    def test_admin_tournament_rollback_restores_backup_reload_model_and_audit(self):
        previous_token = os.environ.get("WORLD_CUP_ADMIN_TOKEN")
        os.environ["WORLD_CUP_ADMIN_TOKEN"] = "secret-token"
        payload = make_compatible_import_payload()
        restored_payload = make_compatible_import_payload()
        restored_payload["teams"][0]["name"] = "回滚后的巴西"
        backup_id = "20260614T080000000000Z"
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_dir = root / "data"
            backup_dir = root / "backups"
            restore_dir = backup_dir / backup_id
            audit_path = root / "admin-audit.jsonl"
            data_dir.mkdir()
            restore_dir.mkdir(parents=True)
            (data_dir / "teams.json").write_text(json.dumps(payload["teams"], ensure_ascii=False), encoding="utf-8")
            (data_dir / "fixtures.json").write_text(json.dumps(payload["fixtures"], ensure_ascii=False), encoding="utf-8")
            (restore_dir / "teams.json").write_text(json.dumps(restored_payload["teams"], ensure_ascii=False), encoding="utf-8")
            (restore_dir / "fixtures.json").write_text(json.dumps(restored_payload["fixtures"], ensure_ascii=False), encoding="utf-8")
            previous_data_dir = getattr(main_module, "runtime_data_dir", None)
            previous_backup_dir = getattr(main_module, "tournament_backup_dir", None)
            previous_audit_path = getattr(main_module, "audit_log_path", None)
            previous_fixtures_path = getattr(main_module, "fixtures_data_path", None)
            main_module.runtime_data_dir = data_dir
            main_module.tournament_backup_dir = backup_dir
            main_module.audit_log_path = audit_path
            main_module.fixtures_data_path = data_dir / "fixtures.json"
            try:
                client = TestClient(app)
                response = client.post(
                    "/api/admin/tournament-data/rollback",
                    headers={"X-Admin-Token": "secret-token"},
                    json={"backupId": backup_id},
                )
                status_response = client.get("/api/model-status")
            finally:
                if previous_data_dir is None:
                    delattr(main_module, "runtime_data_dir")
                else:
                    main_module.runtime_data_dir = previous_data_dir
                if previous_backup_dir is None:
                    delattr(main_module, "tournament_backup_dir")
                else:
                    main_module.tournament_backup_dir = previous_backup_dir
                if previous_audit_path is None:
                    delattr(main_module, "audit_log_path")
                else:
                    main_module.audit_log_path = previous_audit_path
                if previous_fixtures_path is None:
                    delattr(main_module, "fixtures_data_path")
                else:
                    main_module.fixtures_data_path = previous_fixtures_path
                main_module.reload_model_data()
                if previous_token is None:
                    os.environ.pop("WORLD_CUP_ADMIN_TOKEN", None)
                else:
                    os.environ["WORLD_CUP_ADMIN_TOKEN"] = previous_token

            self.assertEqual(response.status_code, 200, response.text)
            result = response.json()
            self.assertEqual(result["restoredBackupId"], backup_id)
            self.assertEqual(json.loads((data_dir / "teams.json").read_text(encoding="utf-8"))[0]["name"], "回滚后的巴西")
            self.assertEqual(status_response.json()["dataset"]["placeholderSlots"], 0)
            self.assertTrue(Path(result["currentBackupDir"]).exists())
            audit_rows = [json.loads(line) for line in audit_path.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(audit_rows[0]["action"], "tournament-data:rollback")
            self.assertEqual(audit_rows[0]["targetId"], backup_id)

    def test_match_prediction_accepts_simulation_count(self):
        client = TestClient(app)
        response = client.get("/api/match-prediction?simulations=1200")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["modelMeta"]["simulationCount"], 1200)
        self.assertEqual(payload["modelMeta"]["changeBaseline"], "unadjusted_model")
        self.assertIn("scoreMatrix", payload)
        self.assertIn("goalMarkets", payload)
        self.assertIn("fairPrices", payload)
        self.assertIn("marketSource", payload)
        self.assertIn("creatorTopics", payload)
        self.assertIn("dailyMovers", payload)
        self.assertEqual(payload["dailyMovers"]["baseline"], "no_previous_snapshot")

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

    def test_upcoming_matches_api_preserves_fixture_venue_metadata(self):
        rows = [
            {
                "home": "brazil",
                "away": "argentina",
                "stage": "小组赛 E 组",
                "kickoff": "2026-06-15T08:00:00-05:00",
                "status": "scheduled",
                "match_no": 31,
                "city": "Mexico City",
                "stadium": "Estadio Azteca",
            }
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            fixtures_path = Path(temp_dir) / "fixtures.json"
            fixtures_path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
            previous_fixtures_path = getattr(main_module, "fixtures_data_path", None)
            main_module.fixtures_data_path = fixtures_path
            try:
                main_module.reload_model_data(main_module.review_data_path, fixtures_path)
                client = TestClient(app)
                response = client.get("/api/upcoming-matches?limit=1")
            finally:
                if previous_fixtures_path is None:
                    delattr(main_module, "fixtures_data_path")
                else:
                    main_module.fixtures_data_path = previous_fixtures_path
                main_module.reload_model_data()

            self.assertEqual(response.status_code, 200)
            item = response.json()["items"][0]
            self.assertEqual(item["matchNo"], 31)
            self.assertEqual(item["city"], "Mexico City")
            self.assertEqual(item["stadium"], "Estadio Azteca")

    def test_finished_matches_api_lists_locked_result_records(self):
        client = TestClient(app)
        response = client.get("/api/finished-matches?limit=3")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["count"], 3)
        first = payload["items"][0]
        self.assertEqual(first["matchNo"], 6)
        self.assertEqual(first["status"], "finished")
        self.assertIsInstance(first["homeScore"], int)
        self.assertIsInstance(first["awayScore"], int)
        self.assertEqual(first["modelUse"], "locked_result_weight")
        self.assertIn("后续路径", first["modelUseLabel"])
        third = payload["items"][2]
        self.assertEqual(third["homeName"], "巴西")
        self.assertEqual(third["homeScore"], 1)
        self.assertEqual(third["awayScore"], 1)
        self.assertEqual(third["awayName"], "摩洛哥")

    def test_match_detail_api_builds_prediction_for_any_scheduled_match(self):
        client = TestClient(app)
        response = client.get("/api/match-detail?home=germany&away=curacao&simulations=1200")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["homeTeam"], "germany")
        self.assertEqual(payload["awayTeam"], "curacao")
        self.assertEqual(payload["homeName"], "德国")
        self.assertEqual(payload["awayName"], "库拉索")
        self.assertEqual(payload["homeCode"], "GER")
        self.assertEqual(payload["awayCode"], "CUW")
        self.assertEqual(len(payload["scoreOutcomes"]), 3)
        self.assertGreater(len(payload["scoreMatrix"]), 0)
        self.assertEqual(len(payload["goalMarkets"]), 4)
        self.assertEqual(len(payload["fairPrices"]), 3)
        self.assertEqual(payload["marketSource"]["status"], "pending")
        self.assertEqual(len(payload["creatorTopics"]), 3)
        self.assertEqual(len(payload["scenarioImpacts"]), 3)
        self.assertEqual(payload["homeWin"] + payload["draw"] + payload["awayWin"], 100)

    def test_match_detail_api_rejects_finished_match_prediction(self):
        client = TestClient(app)
        response = client.get("/api/match-detail?home=mexico&away=south-africa&simulations=1200")

        self.assertEqual(response.status_code, 409)
        self.assertIn("已结束比赛不再预测", response.json()["detail"])

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
