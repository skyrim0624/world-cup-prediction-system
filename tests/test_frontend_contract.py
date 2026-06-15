import json
import re
from pathlib import Path
import unittest


def app_source() -> str:
    return Path("src/App.tsx").read_text(encoding="utf-8")


def styles_source() -> str:
    return Path("src/styles.css").read_text(encoding="utf-8")


def source_between(source: str, start: str, end: str) -> str:
    start_index = source.index(start)
    end_index = source.index(end, start_index)
    return source[start_index:end_index]


def public_home_source() -> str:
    return source_between(app_source(), "function HomePredictionPage()", "function TeamFlag")


def flag_asset_map(source: str, const_name: str) -> dict[str, str]:
    object_source = source_between(source, f"const {const_name}", "};")
    entries: dict[str, str] = {}
    for match in re.finditer(r'(?:"([^"]+)"|([a-z][a-z0-9]*)):\s*"([^"]+)"', object_source):
        key = match.group(1) or match.group(2)
        entries[key] = match.group(3)
    return entries


class FrontendContractTest(unittest.TestCase):
    def test_public_homepage_uses_public_schedule_api_only(self):
        source = public_home_source()

        self.assertIn("/api/public-upcoming-matches?limit=12", source)
        self.assertNotIn("/api/match-prediction", source)
        self.assertNotIn("/api/upcoming-matches?limit=12", source)
        self.assertNotIn("/api/match-detail", source)
        self.assertNotIn("/api/access-options", source)
        self.assertNotIn("/api/payments/config", source)
        self.assertNotIn("/api/payments/orders", source)

    def test_public_homepage_hides_paid_prediction_content(self):
        source = public_home_source()

        self.assertIn("¥1", source)
        self.assertIn("查看预测", source)
        self.assertIn("全包剩余 92 场 ¥39", source)
        self.assertIn("安全支付", source)
        self.assertNotIn("homeWin", source)
        self.assertNotIn("draw", source)
        self.assertNotIn("awayWin", source)
        self.assertNotIn("topScore", source)
        self.assertNotIn("scoreOutcomes", source)
        self.assertNotIn("最可能", source)
        self.assertNotIn("比分", source)
        self.assertNotIn("概率", source)

    def test_public_homepage_keeps_operations_content_out(self):
        source = public_home_source()

        self.assertNotIn("/admin", source)
        self.assertNotIn("/api/finished-matches", source)
        self.assertNotIn("赛果记录", source)
        self.assertNotIn("真实模型", source)
        self.assertNotIn("入模", source)
        self.assertNotIn("忽略", source)
        self.assertNotIn("次模拟", source)
        self.assertNotIn("后台", source)

    def test_public_homepage_matches_01_mobile_visual_structure(self):
        source = public_home_source()
        styles = styles_source()

        self.assertIn("public-match-shell", source)
        self.assertIn("public-match-app", source)
        self.assertIn("public-match-header", source)
        self.assertIn("public-match-list", source)
        self.assertIn("public-pass-bar", source)
        self.assertIn("未开赛比赛", source)
        self.assertIn("世界杯预测", source)
        self.assertIn('url("/assets/app/stadium-bg-mobile-portrait.png")', styles)
        self.assertIn("width: min(100%, 430px)", styles)
        self.assertIn("font-size: 24px", styles)
        self.assertIn("min-height: 34px", styles)
        self.assertIn("grid-template-columns: 76px minmax(0, 1fr) 80px", styles)
        self.assertIn("min-height: 80px", styles)
        self.assertNotIn("grid-template-columns: 92px minmax(0, 1fr) 90px", styles)
        self.assertIn("grid-template-columns: repeat(3, minmax(0, 1fr))", styles)
        self.assertIn("bottom: max(31px, calc(env(safe-area-inset-bottom) + 31px))", styles)

    def test_public_fallback_strips_paid_fields(self):
        source = app_source()
        strip_source = source_between(source, "function toPublicUpcomingMatch", "function comparePublicUpcomingMatches")

        self.assertIn("stage: match.stage", strip_source)
        self.assertIn("homeName: match.homeName", strip_source)
        self.assertIn("awayName: match.awayName", strip_source)
        self.assertNotIn("homeWin", strip_source)
        self.assertNotIn("draw", strip_source)
        self.assertNotIn("awayWin", strip_source)
        self.assertNotIn("topScore", strip_source)

    def test_app_exposes_single_match_route_for_next_page(self):
        source = app_source()
        single_match_source = source_between(source, "function SingleMatchPage", "function LockedPreviewRow")

        self.assertIn("/match/", source)
        self.assertIn("/checkout/", source)
        self.assertIn("/api/public-match-summary", single_match_source)
        self.assertIn("/api/payments/orders", single_match_source)
        self.assertIn("checkoutPagePath", single_match_source)
        self.assertIn("完整预测需支付后查看", single_match_source)
        self.assertIn("¥1 解锁本场", single_match_source)
        self.assertIn("全包剩余 92 场 ¥39", single_match_source)
        self.assertNotIn("/api/match-detail", single_match_source)
        self.assertIn("SingleMatchPage", source)
        self.assertIn("matchPagePath", source)

    def test_checkout_page_uses_payment_config_and_match_scope(self):
        source = app_source()
        checkout_source = source_between(source, "function SingleMatchCheckoutPage", "function PaymentInfoRow")
        styles = styles_source()

        self.assertIn("/api/public-match-summary", checkout_source)
        self.assertIn("/api/access-options", checkout_source)
        self.assertIn("/api/payments/config", checkout_source)
        self.assertIn("/api/payments/orders", checkout_source)
        self.assertIn("contentKey: \"match_prediction\"", checkout_source)
        self.assertIn("matchKey", checkout_source)
        self.assertIn("微信支付", checkout_source)
        self.assertIn("支付宝支付", checkout_source)
        self.assertIn("创建支付订单", checkout_source)
        self.assertIn("zhugejunshi.com", checkout_source)
        self.assertNotIn("homeWin", checkout_source)
        self.assertNotIn("draw", checkout_source)
        self.assertNotIn("awayWin", checkout_source)
        self.assertNotIn("topScore", checkout_source)
        self.assertNotIn("missingConfig", checkout_source)
        self.assertNotIn("CUSTOMER_", checkout_source)
        self.assertIn("checkout-page-shell", styles)
        self.assertIn("gold-football-product-icon.png", styles + checkout_source)
        self.assertIn("gold-payment-button-texture.png", styles)

    def test_payment_pending_page_syncs_order_and_invokes_wechat_jsapi(self):
        source = app_source()
        payment_source = source_between(source, "function PaymentPendingPage", "function AdminConsole")

        self.assertIn("sync=1", payment_source)
        self.assertIn("jsapiParams", payment_source)
        self.assertIn("invokeWechatJsapiPay", payment_source)
        self.assertIn("WeixinJSBridge", source)
        self.assertIn("getBrandWCPayRequest", source)
        self.assertIn("/api/payments/orders/", payment_source)
        polling_source = source_between(payment_source, "async function loadActiveOrder()", "return () =>")
        self.assertIn("await loadOrder(true)", polling_source)

    def test_team_flags_cover_tournament_teams_and_match_lists(self):
        source = app_source()
        teams = json.loads(Path("backend/data_files/teams.json").read_text(encoding="utf-8"))

        self.assertIn("TEAM_FLAG_ASSET_BY_KEY", source)
        self.assertIn("flagSource", source)
        self.assertIn("src={flagSource}", source)
        self.assertIn("TeamFlag team={match.homeTeam} code={match.homeCode}", source)
        self.assertIn("TeamFlag team={match.awayTeam} code={match.awayCode}", source)
        self.assertIn("TeamFlag team={detail.homeTeam} code={detail.homeCode}", source)
        self.assertIn("TeamFlag team={detail.awayTeam} code={detail.awayCode}", source)
        self.assertNotIn("knownFlags", source)
        self.assertIn('loading="eager"', source)
        for team in teams:
            self.assertRegex(source, rf'["\']?{re.escape(team["key"])}["\']?:')

    def test_team_flag_mappings_resolve_to_existing_assets(self):
        source = app_source()
        teams = json.loads(Path("backend/data_files/teams.json").read_text(encoding="utf-8"))
        assets_dir = Path("public/assets/flags")
        key_map = flag_asset_map(source, "TEAM_FLAG_ASSET_BY_KEY")
        code_map = flag_asset_map(source, "TEAM_FLAG_ASSET_BY_CODE")

        missing = []
        for team in teams:
            asset = key_map.get(team["key"]) or code_map.get(team["code"])
            if not asset or not (assets_dir / f"{asset}.png").exists():
                missing.append(f'{team["name"]}({team["key"]}/{team["code"]})')

        self.assertEqual([], missing)


if __name__ == "__main__":
    unittest.main()
