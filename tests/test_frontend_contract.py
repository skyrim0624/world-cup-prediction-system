from pathlib import Path
import unittest


def app_source() -> str:
    return Path("src/App.tsx").read_text(encoding="utf-8")


def source_between(source: str, start: str, end: str) -> str:
    start_index = source.index(start)
    end_index = source.index(end, start_index)
    return source[start_index:end_index]


class FrontendContractTest(unittest.TestCase):
    def test_homepage_renders_paid_access_boundary(self):
        source = app_source()
        self.assertIn("/api/access-options", source)
        self.assertIn("/api/payments/config", source)
        self.assertIn("/api/payments/orders", source)
        self.assertIn("付费解锁", source)
        self.assertIn("微信支付", source)
        self.assertIn("支付宝支付", source)
        self.assertIn("扫码付款", source)
        self.assertIn("AccessPanel", source)

    def test_app_exposes_single_match_page_route(self):
        source = app_source()
        self.assertIn("/match/", source)
        self.assertIn("/api/match-detail", source)
        self.assertIn("SingleMatchPage", source)
        self.assertIn("matchPagePath", source)
        self.assertIn("打开单场页", source)

    def test_homepage_renders_finished_match_records(self):
        source = app_source()
        self.assertIn("/api/finished-matches", source)
        self.assertIn("已结束比赛记录", source)
        self.assertIn("FinishedMatchesPanel", source)

    def test_homepage_renders_daily_probability_movers(self):
        source = app_source()
        self.assertIn("今日概率变化", source)
        self.assertIn("DailyMoversPanel", source)
        self.assertIn("dailyMovers", source)
        self.assertIn("reasons", source)
        self.assertIn("mover-reasons", source)

    def test_public_homepage_is_user_prediction_page_not_ops_console(self):
        source = app_source()
        home_source = source_between(source, "function HomePredictionPage()", "function UpcomingMatchesPanel")

        self.assertIn("今日重点比赛", home_source)
        self.assertIn("用户预测页", home_source)
        self.assertIn("免费预览", home_source)
        self.assertIn("解锁完整预测", home_source)
        self.assertNotIn("EventReviewPanel", home_source)
        self.assertNotIn("onRebuildSnapshot", home_source)
        self.assertNotIn("双击移动模块", home_source)
        self.assertNotIn("DraggablePanel", home_source)

    def test_public_homepage_uses_world_cup_portal_visual_language(self):
        source = app_source()
        styles = Path("src/styles.css").read_text(encoding="utf-8")
        home_source = source_between(source, "function HomePredictionPage()", "function UpcomingMatchesPanel")

        self.assertIn("worldcup-hero", home_source)
        self.assertIn("2026", home_source)
        self.assertIn("美加墨", home_source)
        self.assertIn("FIFA World Cup 2026", home_source)
        self.assertIn("portal-grid", home_source)
        self.assertIn("section-title", home_source)
        self.assertIn("全部赛程", home_source)
        self.assertIn("/assets/world-cup-hero.png", styles)
        self.assertIn("featured-photo-card", styles)

    def test_single_match_page_is_paid_conversion_page_with_locked_content(self):
        source = app_source()
        single_match_source = source_between(source, "function SingleMatchPage", "function AdminConsole")

        self.assertIn("免费预览", single_match_source)
        self.assertIn("完整预测", single_match_source)
        self.assertIn("LockedContent", single_match_source)
        self.assertIn('contentKey="match_prediction"', single_match_source)
        self.assertIn("AccessPanel", single_match_source)

    def test_payment_flow_polls_order_and_checks_access_decision(self):
        source = app_source()

        self.assertIn("PAYMENT_STATUS_POLL_MS", source)
        self.assertIn("pollPaymentOrder", source)
        self.assertIn("/api/payments/orders/", source)
        self.assertIn("/api/access-decision", source)
        self.assertIn("unlockDecisions", source)


if __name__ == "__main__":
    unittest.main()
