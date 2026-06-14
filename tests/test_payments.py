import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

import backend.main as main_module
from backend.payments import PAYMENT_ORDERS, build_order_access_decision, create_payment_order, get_payment_order, update_payment_order_status
from backend.main import app


class PaymentApiTest(unittest.TestCase):
    def test_payment_config_lists_wechat_and_alipay_scan_providers(self):
        client = TestClient(app)

        response = client.get("/api/payments/config")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual([provider["provider"] for provider in payload["providers"]], ["wechat", "alipay"])
        self.assertFalse(payload["ready"])
        self.assertFalse(payload["providers"][0]["configured"])
        self.assertIn("CUSTOMER_WECHAT_PAY_CREATE_URL", payload["providers"][0]["missingConfig"])
        self.assertFalse(payload["providers"][1]["configured"])
        self.assertIn("CUSTOMER_ALIPAY_PAY_CREATE_URL", payload["providers"][1]["missingConfig"])

    def test_create_scan_payment_order_requires_real_provider_configuration(self):
        client = TestClient(app)

        response = client.post(
            "/api/payments/orders",
            json={"productKey": "single_match", "provider": "wechat"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["productKey"], "single_match")
        self.assertEqual(payload["provider"], "wechat")
        self.assertEqual(payload["status"], "provider_config_required")
        self.assertIsNone(payload["qrCodeUrl"])
        self.assertIn("客户微信支付接口", payload["nextAction"])
        self.assertIn("amountLabel", payload)
        self.assertEqual(payload["paymentMethod"], "scan_qr")
        self.assertEqual(payload["integrationOwner"], "customer")

    def test_payment_order_status_can_be_queried_after_creation(self):
        client = TestClient(app)
        created = client.post(
            "/api/payments/orders",
            json={"productKey": "tournament_pass", "provider": "alipay"},
        ).json()

        response = client.get(f"/api/payments/orders/{created['orderId']}")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["orderId"], created["orderId"])
        self.assertEqual(payload["provider"], "alipay")
        self.assertEqual(payload["status"], "provider_config_required")

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
            "wechat",
            env={
                "CUSTOMER_WECHAT_PAY_CREATE_URL": "https://customer.example/pay/wechat/create",
                "CUSTOMER_WECHAT_PAY_STATUS_URL": "https://customer.example/pay/wechat/status",
                "CUSTOMER_WECHAT_PAY_NOTIFY_SECRET": "secret",
            },
        )

        self.assertEqual(order["status"], "customer_interface_ready")
        self.assertIsNone(order["qrCodeUrl"])
        self.assertIn("客户微信支付接口已配置", order["nextAction"])

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
            denied = build_order_access_decision(created["orderId"], "tournament_probabilities", storage_path=store_path)

        self.assertTrue(allowed["allowed"])
        self.assertEqual(allowed["reason"], "allowed")
        self.assertFalse(denied["allowed"])
        self.assertEqual(denied["reason"], "product_not_in_scope")

    def test_payment_order_api_persists_created_order(self):
        client = TestClient(app)
        with TemporaryDirectory() as temp_dir:
            store_path = Path(temp_dir) / "payment-orders.json"
            previous_path = main_module.payment_orders_path
            main_module.payment_orders_path = store_path
            try:
                created = client.post("/api/payments/orders", json={"productKey": "single_match", "provider": "wechat"}).json()
                PAYMENT_ORDERS.clear()

                response = client.get(f"/api/payments/orders/{created['orderId']}")
            finally:
                main_module.payment_orders_path = previous_path

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["orderId"], created["orderId"])

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
