import json
import re
from pathlib import Path
import unittest


def app_source() -> str:
    return Path("src/App.tsx").read_text(encoding="utf-8")


def source_between(source: str, start: str, end: str) -> str:
    start_index = source.index(start)
    end_index = source.index(end, start_index)
    return source[start_index:end_index]


class FrontendContractTest(unittest.TestCase):
    def test_public_app_hides_paid_access_boundary(self):
        source = app_source()
        home_source = source_between(source, "function HomePredictionPage()", "function TeamFlag")
        single_match_source = source_between(source, "function SingleMatchPage", "function AdminConsole")

        self.assertIn("VITE_API_BASE_URL", source)
        self.assertNotIn("/api/access-options", home_source)
        self.assertNotIn("/api/payments/config", source)
        self.assertNotIn("/api/payments/orders", source)
        self.assertNotIn("/api/access-decision", source)
        self.assertNotIn("付费解锁", source)
        self.assertNotIn("微信支付", source)
        self.assertNotIn("支付宝支付", source)
        self.assertNotIn("扫码付款", source)
        self.assertNotIn("AccessPanel", source)
        self.assertNotIn("LockedContent", source)
        self.assertNotIn("解锁", home_source)
        self.assertNotIn("解锁", single_match_source)

    def test_app_exposes_single_match_page_route(self):
        source = app_source()
        self.assertIn("/match/", source)
        self.assertIn("/api/match-detail", source)
        self.assertIn("SingleMatchPage", source)
        self.assertIn("matchPagePath", source)
        self.assertIn("打开单场页", source)

    def test_homepage_keeps_operations_content_out_of_public_app(self):
        source = app_source()
        home_source = source_between(source, "function HomePredictionPage()", "function TeamFlag")

        self.assertNotIn("/api/finished-matches", home_source)
        self.assertNotIn("赛果记录", home_source)
        self.assertNotIn("FinishedMatchesPanel", home_source)
        self.assertNotIn("真实模型", home_source)
        self.assertNotIn("入模", home_source)
        self.assertNotIn("忽略", home_source)
        self.assertNotIn("次模拟", home_source)
        self.assertNotIn("市场价格源待接入", source)

    def test_board_page_omits_daily_probability_placeholder(self):
        source = app_source()
        home_source = source_between(source, "function HomePredictionPage()", "function UpcomingMatchesPanel")

        self.assertIn("冠军概率榜", home_source)
        self.assertNotIn("今日概率变化", home_source)
        self.assertNotIn("DailyMoversPanel", source)
        self.assertNotIn("等待下一次日更快照生成今日变化", source)
        self.assertIn("dailyMovers", source)

    def test_public_homepage_is_user_prediction_page_not_ops_console(self):
        source = app_source()
        home_source = source_between(source, "function HomePredictionPage()", "function UpcomingMatchesPanel")

        self.assertIn("今日重点预测", home_source)
        self.assertIn("app-bottom-nav", home_source)
        self.assertIn("预测功能导航", home_source)
        self.assertIn('hash: "matches"', source)
        self.assertNotIn("activeScreenConfig.label", home_source)
        self.assertIn("进球概率", home_source)
        self.assertIn("新闻与方法", home_source)
        self.assertIn("判断依据", home_source)
        self.assertIn("UserMethodPanel", source)
        self.assertNotIn("模型方法", home_source)
        self.assertNotIn("路径传导", home_source)
        self.assertNotIn("EventReviewPanel", home_source)
        self.assertNotIn("onRebuildSnapshot", home_source)
        self.assertNotIn("双击移动模块", home_source)
        self.assertNotIn("DraggablePanel", home_source)

    def test_public_homepage_uses_world_cup_portal_visual_language(self):
        source = app_source()
        styles = Path("src/styles.css").read_text(encoding="utf-8")
        home_source = source_between(source, "function HomePredictionPage()", "function UpcomingMatchesPanel")

        self.assertIn("世界杯预测", home_source)
        self.assertIn("app-screen", home_source)
        self.assertIn("app-screen-stack", home_source)
        self.assertIn("app-probability-row", home_source)
        self.assertIn("section-title", home_source)
        self.assertIn("app-mini-market", home_source)
        self.assertNotIn("World Cup Forecast Desk", home_source)
        self.assertNotIn("赛果记录", home_source)
        self.assertIn("app-bottom-nav", styles)
        self.assertIn("grid-template-columns: repeat(4, minmax(0, 1fr))", styles)
        self.assertIn("grid-template-columns: repeat(2, minmax(0, 1fr))", styles)
        self.assertIn("width: min(100%, 460px)", styles)
        self.assertIn("font-size: clamp(15px, 4vw, 18px)", styles)
        self.assertIn("font-size: clamp(21px, 6vw, 26px)", styles)

    def test_team_flags_cover_tournament_teams_and_match_lists(self):
        source = app_source()
        teams = json.loads(Path("backend/data_files/teams.json").read_text(encoding="utf-8"))

        self.assertIn("TEAM_FLAG_ASSET_BY_KEY", source)
        self.assertIn("flagSource", source)
        self.assertIn("src={flagSource}", source)
        self.assertIn("TeamFlag team={homeTeam.key} code={homeTeam.code}", source)
        self.assertIn("TeamFlag team={awayTeam.key} code={awayTeam.code}", source)
        self.assertIn("TeamFlag team={match.homeTeam} code={match.homeCode}", source)
        self.assertIn("TeamFlag team={match.awayTeam} code={match.awayCode}", source)
        self.assertIn("TeamFlag team={detail.homeTeam} code={detail.homeCode}", source)
        self.assertIn("TeamFlag team={detail.awayTeam} code={detail.awayCode}", source)
        self.assertNotIn("knownFlags", source)
        for team in teams:
            self.assertRegex(source, rf'["\']?{re.escape(team["key"])}["\']?:')

    def test_single_match_page_shows_prediction_without_paid_gate(self):
        source = app_source()
        single_match_source = source_between(source, "function SingleMatchPage", "function AdminConsole")

        self.assertIn("赛前胜平负概率", single_match_source)
        self.assertIn("比分预测", single_match_source)
        self.assertIn("单场预测细节", single_match_source)
        self.assertIn("match-full-content", single_match_source)
        self.assertNotIn("免费预览", single_match_source)
        self.assertNotIn("付费解锁", single_match_source)
        self.assertNotIn("完整比分分布需要解锁", single_match_source)
        self.assertNotIn("LockedContent", single_match_source)
        self.assertNotIn('contentKey="match_prediction"', single_match_source)
        self.assertNotIn("AccessPanel", single_match_source)

    def test_public_frontend_omits_payment_flow(self):
        source = app_source()

        self.assertNotIn("PAYMENT_STATUS_POLL_MS", source)
        self.assertNotIn("pollPaymentOrder", source)
        self.assertNotIn("/api/payments/orders/", source)
        self.assertNotIn("/api/access-decision", source)
        self.assertNotIn("unlockDecisions", source)


if __name__ == "__main__":
    unittest.main()
