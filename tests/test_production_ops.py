import json
import tempfile
import unittest
from pathlib import Path


class ProductionOpsTest(unittest.TestCase):
    def test_atomic_json_write_replaces_existing_payload_without_leftover_temp_files(self):
        from backend.io_utils import write_json_atomic

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "payload.json"
            path.write_text('{"status":"old"}', encoding="utf-8")

            write_json_atomic(path, {"status": "new", "count": 2})

            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), {"status": "new", "count": 2})
            self.assertEqual(list(Path(temp_dir).glob("*.tmp")), [])

    def test_daily_update_lock_rejects_overlapping_run_without_changing_status(self):
        from backend.daily_update import FeedSpec, run_daily_update
        from backend.io_utils import acquire_process_lock

        feed = """<?xml version="1.0" encoding="UTF-8" ?>
<rss version="2.0"><channel><item>
  <title>法国中卫恢复合练</title>
  <description>法国中卫恢复合练。</description>
  <link>https://example.com/france-recovery</link>
</item></channel></rss>
"""
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            lock_path = root / "daily-update.lock"
            status_path = root / "daily-update-status.json"
            raw_news_path = root / "raw-news.json"
            snapshot_path = root / "latest-match-prediction.json"
            feed_path = root / "feed.xml"
            raw_news_path.write_text("[]", encoding="utf-8")
            status_path.write_text('{"status":"success","updatedAt":"2026-06-14T08:00:00Z"}', encoding="utf-8")
            feed_path.write_text(feed, encoding="utf-8")

            with acquire_process_lock(lock_path):
                report = run_daily_update(
                    raw_news_path=raw_news_path,
                    snapshot_path=snapshot_path,
                    feed_specs=[FeedSpec(input_path=feed_path, source="reuters")],
                    simulation_count=1200,
                    status_path=status_path,
                    lock_path=lock_path,
                )

            self.assertEqual(report["status"], "skipped")
            self.assertEqual(report["reason"], "already_running")
            self.assertEqual(json.loads(status_path.read_text(encoding="utf-8"))["status"], "success")

    def test_production_readiness_requires_fresh_status_and_valid_snapshot(self):
        from backend.production_health import build_production_readiness

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            status_path = root / "daily-update-status.json"
            snapshot_path = root / "latest-match-prediction.json"
            status_path.write_text(
                json.dumps(
                    {"status": "success", "updatedAt": "2026-06-14T08:00:00Z"},
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            readiness = build_production_readiness(
                status_path=status_path,
                snapshot_path=snapshot_path,
                now_iso="2026-06-14T09:00:00Z",
                max_status_age_hours=2,
            )

            self.assertEqual(readiness["status"], "fail")
            self.assertEqual(readiness["checks"]["dailyStatus"]["status"], "pass")
            self.assertEqual(readiness["checks"]["snapshot"]["status"], "fail")

    def test_model_quality_report_default_path_is_packaged_with_backend_root(self):
        from backend.production_health import DEFAULT_MODEL_QUALITY_REPORT_PATH

        self.assertEqual(DEFAULT_MODEL_QUALITY_REPORT_PATH.name, "model-quality-report.json")
        self.assertEqual(DEFAULT_MODEL_QUALITY_REPORT_PATH.parent.name, "reports")
        self.assertTrue(str(DEFAULT_MODEL_QUALITY_REPORT_PATH).endswith("reports/model-quality-report.json"))

    def test_tencent_deployment_pack_is_present(self):
        required_paths = [
            Path("Dockerfile"),
            Path("docker-compose.tencent.yml"),
            Path(".env.production.example"),
            Path("deploy/tencent-cloud/nginx.conf"),
            Path("deploy/tencent-cloud/world-cup-prediction-api.service"),
            Path("deploy/tencent-cloud/world-cup-prediction-daily.service"),
            Path("deploy/tencent-cloud/world-cup-prediction-daily.timer"),
            Path("docs/腾讯云生产部署说明.md"),
        ]

        for path in required_paths:
            self.assertTrue(path.exists(), f"缺少生产部署文件: {path}")

    def test_package_exposes_tencent_production_commands(self):
        package = json.loads(Path("package.json").read_text(encoding="utf-8"))
        scripts = package["scripts"]

        self.assertIn("production:check", scripts)
        self.assertIn("production:serve", scripts)
        self.assertIn("daily:update:production", scripts)
        self.assertIn("WORLD_CUP_SERVE_STATIC=1", scripts["production:serve"])


if __name__ == "__main__":
    unittest.main()
