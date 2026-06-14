from pathlib import Path
import unittest


class FrontendContractTest(unittest.TestCase):
    def test_homepage_renders_paid_access_boundary(self):
        app_source = Path("src/App.tsx").read_text(encoding="utf-8")
        self.assertIn("/api/access-options", app_source)
        self.assertIn("/api/payments/config", app_source)
        self.assertIn("/api/payments/orders", app_source)
        self.assertIn("付费解锁", app_source)
        self.assertIn("微信支付", app_source)
        self.assertIn("支付宝支付", app_source)
        self.assertIn("扫码付款", app_source)
        self.assertIn("AccessPanel", app_source)

    def test_app_exposes_single_match_page_route(self):
        app_source = Path("src/App.tsx").read_text(encoding="utf-8")
        self.assertIn("/match/", app_source)
        self.assertIn("/api/match-detail", app_source)
        self.assertIn("SingleMatchPage", app_source)
        self.assertIn("matchPagePath", app_source)
        self.assertIn("打开单场页", app_source)

    def test_homepage_renders_finished_match_records(self):
        app_source = Path("src/App.tsx").read_text(encoding="utf-8")
        self.assertIn("/api/finished-matches", app_source)
        self.assertIn("已结束比赛记录", app_source)
        self.assertIn("FinishedMatchesPanel", app_source)

    def test_homepage_renders_daily_probability_movers(self):
        app_source = Path("src/App.tsx").read_text(encoding="utf-8")
        self.assertIn("今日概率变化", app_source)
        self.assertIn("DailyMoversPanel", app_source)
        self.assertIn("dailyMovers", app_source)
        self.assertIn("reasons", app_source)
        self.assertIn("mover-reasons", app_source)


if __name__ == "__main__":
    unittest.main()
