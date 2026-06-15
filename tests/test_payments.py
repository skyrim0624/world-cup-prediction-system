import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

import backend.main as main_module
from backend.payments import PAYMENT_ORDERS, build_order_access_decision, create_payment_order, get_payment_order, update_payment_order_status
from backend.main import app


class PaymentApiTest(unittest.TestCase):
    def test_payment_config_lists_customer_required_payment_providers(self):
        client = TestClient(app)

        response = client.get("/api/payments/config")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual([provider["provider"] for provider in payload["providers"]], ["wechat_jsapi", "wechat_native", "alipay_qr"])
        self.assertEqual([provider["paymentMethod"] for provider in payload["providers"]], ["jsapi", "native", "scan_qr"])
        self.assertFalse(payload["ready"])
        self.assertFalse(payload["providers"][0]["configured"])
        self.assertIn("CUSTOMER_WECHAT_JSAPI_PAY_CREATE_URL", payload["providers"][0]["missingConfig"])
        self.assertFalse(payload["providers"][2]["configured"])
        self.assertIn("CUSTOMER_ALIPAY_QR_PAY_CREATE_URL", payload["providers"][2]["missingConfig"])

    def test_create_scan_payment_order_requires_real_provider_configuration(self):
        client = TestClient(app)

        response = client.post(
            "/api/payments/orders",
            json={"productKey": "single_match", "provider": "wechat_native"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["productKey"], "single_match")
        self.assertEqual(payload["provider"], "wechat_native")
        self.assertEqual(payload["status"], "provider_config_required")
        self.assertIsNone(payload["qrCodeUrl"])
        self.assertIn("客户微信 Native 支付接口", payload["nextAction"])
        self.assertEqual(payload["amountLabel"], "¥1.00")
        self.assertEqual(payload["paymentMethod"], "native")
        self.assertEqual(payload["paymentMethodLabel"], "扫码支付")
        self.assertEqual(payload["integrationOwner"], "customer")

    def test_payment_order_status_can_be_queried_after_creation(self):
        client = TestClient(app)
        created = client.post(
            "/api/payments/orders",
            json={"productKey": "tournament_pass", "provider": "alipay_qr"},
        ).json()

        response = client.get(f"/api/payments/orders/{created['orderId']}")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["orderId"], created["orderId"])
        self.assertEqual(payload["provider"], "alipay_qr")
        self.assertEqual(payload["status"], "provider_config_required")
        self.assertEqual(payload["amountLabel"], "¥39.00")

    def test_payment_order_rejects_unknown_provider_or_product(self):
        client = TestClient(app)

        unknown_provider = client.post(
            "/api/payments/orders",
            json={"productKey": "single_match", "provider": "stripe"},
        )
        unknown_product = client.post(
            "/api/payments/orders",
            json={"productKey": "vip", "provider": "wechat"},
        )

        self.assertEqual(unknown_provider.status_code, 400)
        self.assertIn("未知支付渠道", unknown_provider.json()["detail"])
        self.assertEqual(unknown_product.status_code, 400)
        self.assertIn("未知付费产品", unknown_product.json()["detail"])

    def test_configured_customer_interface_does_not_fabricate_qr_code(self):
        order = create_payment_order(
            "single_match",
            "wechat_native",
            env={
                "CUSTOMER_WECHAT_NATIVE_PAY_CREATE_URL": "https://customer.example/pay/wechat/create",
                "CUSTOMER_WECHAT_NATIVE_PAY_STATUS_URL": "https://customer.example/pay/wechat/status",
                "CUSTOMER_WECHAT_NATIVE_PAY_NOTIFY_SECRET": "secret",
            },
        )

        self.assertEqual(order["status"], "customer_interface_ready")
        self.assertIsNone(order["qrCodeUrl"])
        self.assertIn("客户微信 Native 支付接口已配置", order["nextAction"])

    def test_payment_order_can_persist_match_context_for_waiting_page(self):
        order = create_payment_order(
            "single_match",
            "wechat_native",
            metadata={
                "contentKey": "match_prediction",
                "matchKey": "netherlands-japan",
                "homeTeam": "netherlands",
                "awayTeam": "japan",
                "homeName": "荷兰",
                "awayName": "日本",
                "ignored": "不应写入",
            },
        )

        self.assertEqual(order["metadata"]["contentKey"], "match_prediction")
        self.assertEqual(order["metadata"]["matchKey"], "netherlands-japan")
        self.assertEqual(order["metadata"]["homeName"], "荷兰")
        self.assertEqual(order["metadata"]["awayName"], "日本")
        self.assertNotIn("ignored", order["metadata"])

    def test_payment_order_persists_to_json_store(self):
        with TemporaryDirectory() as temp_dir:
            store_path = Path(temp_dir) / "payment-orders.json"
            created = create_payment_order("single_match", "wechat", storage_path=store_path)
            PAYMENT_ORDERS.clear()

            loaded = get_payment_order(created["orderId"], storage_path=store_path)

        self.assertEqual(loaded["orderId"], created["orderId"])
        self.assertEqual(loaded["productKey"], "single_match")

    def test_unpaid_order_does_not_unlock_content(self):
        with TemporaryDirectory() as temp_dir:
            store_path = Path(temp_dir) / "payment-orders.json"
            created = create_payment_order("single_match", "wechat", storage_path=store_path)

            decision = build_order_access_decision(created["orderId"], "match_prediction", storage_path=store_path)

        self.assertFalse(decision["allowed"])
        self.assertEqual(decision["reason"], "order_not_paid")
        self.assertEqual(decision["paymentStatus"], "provider_config_required")

    def test_paid_order_unlocks_covered_content_only(self):
        with TemporaryDirectory() as temp_dir:
            store_path = Path(temp_dir) / "payment-orders.json"
            created = create_payment_order("single_match", "wechat", storage_path=store_path)
            update_payment_order_status(created["orderId"], "paid", storage_path=store_path)

            allowed = build_order_access_decision(created["orderId"], "match_prediction", storage_path=store_path)
            review_allowed = build_order_access_decision(created["orderId"], "post_match_review", storage_path=store_path)
            denied = build_order_access_decision(created["orderId"], "tournament_probabilities", storage_path=store_path)

        self.assertTrue(allowed["allowed"])
        self.assertEqual(allowed["reason"], "allowed")
        self.assertTrue(review_allowed["allowed"])
        self.assertEqual(review_allowed["reason"], "allowed")
        self.assertFalse(denied["allowed"])
        self.assertEqual(denied["reason"], "product_not_in_scope")

    def test_paid_single_match_order_is_scoped_to_match_key_when_present(self):
        with TemporaryDirectory() as temp_dir:
            store_path = Path(temp_dir) / "payment-orders.json"
            created = create_payment_order(
                "single_match",
                "wechat",
                metadata={"contentKey": "match_prediction", "matchKey": "netherlands-japan"},
                storage_path=store_path,
            )
            update_payment_order_status(created["orderId"], "paid", storage_path=store_path)

            allowed = build_order_access_decision(created["orderId"], "match_prediction", match_key="netherlands-japan", storage_path=store_path)
            denied = build_order_access_decision(created["orderId"], "match_prediction", match_key="germany-curacao", storage_path=store_path)

        self.assertTrue(allowed["allowed"])
        self.assertEqual(allowed["reason"], "allowed")
        self.assertFalse(denied["allowed"])
        self.assertEqual(denied["reason"], "match_not_in_scope")

    def test_payment_order_api_persists_created_order(self):
        client = TestClient(app)
        with TemporaryDirectory() as temp_dir:
            store_path = Path(temp_dir) / "payment-orders.json"
            previous_path = main_module.payment_orders_path
            main_module.payment_orders_path = store_path
            try:
                created = client.post(
                    "/api/payments/orders",
                    json={
                        "productKey": "single_match",
                        "provider": "wechat",
                        "contentKey": "match_prediction",
                        "matchKey": "netherlands-japan",
                        "homeTeam": "netherlands",
                        "awayTeam": "japan",
                        "homeName": "荷兰",
                        "awayName": "日本",
                    },
                ).json()
                PAYMENT_ORDERS.clear()

                response = client.get(f"/api/payments/orders/{created['orderId']}")
            finally:
                main_module.payment_orders_path = previous_path

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["orderId"], created["orderId"])
        self.assertEqual(response.json()["metadata"]["matchKey"], "netherlands-japan")

    def test_access_decision_api_uses_payment_order_status(self):
        client = TestClient(app)
        created = client.post("/api/payments/orders", json={"productKey": "single_match", "provider": "wechat"}).json()

        response = client.get(
            "/api/access-decision",
            params={"orderId": created["orderId"], "contentKey": "match_prediction"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertFalse(payload["allowed"])
        self.assertEqual(payload["reason"], "order_not_paid")
        self.assertEqual(payload["productKey"], "single_match")


if __name__ == "__main__":
    unittest.main()
