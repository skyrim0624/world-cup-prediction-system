import unittest
from datetime import UTC, datetime

from backend.daily_health import build_daily_update_health


class AdminOverviewTest(unittest.TestCase):
    def test_daily_update_health_marks_missing_status(self):
        health = build_daily_update_health(None, datetime(2026, 6, 14, 12, 0, tzinfo=UTC))

        self.assertEqual(health["status"], "missing")
        self.assertEqual(health["label"], "未执行")

    def test_daily_update_health_marks_fresh_success_status(self):
        health = build_daily_update_health(
            {"status": "success", "updatedAt": "2026-06-14T02:00:00Z"},
            datetime(2026, 6, 14, 12, 0, tzinfo=UTC),
        )

        self.assertEqual(health["status"], "fresh")
        self.assertEqual(health["hoursSinceUpdate"], 10)

    def test_daily_update_health_marks_stale_success_status(self):
        health = build_daily_update_health(
            {"status": "success", "updatedAt": "2026-06-13T00:00:00Z"},
            datetime(2026, 6, 14, 12, 0, tzinfo=UTC),
        )

        self.assertEqual(health["status"], "stale")
        self.assertEqual(health["label"], "过期")

    def test_daily_update_health_marks_failed_status(self):
        health = build_daily_update_health(
            {"status": "failed", "updatedAt": "2026-06-14T10:00:00Z", "error": "feed missing"},
            datetime(2026, 6, 14, 12, 0, tzinfo=UTC),
        )

        self.assertEqual(health["status"], "failed")
        self.assertEqual(health["label"], "失败")
        self.assertEqual(health["message"], "feed missing")


if __name__ == "__main__":
    unittest.main()
