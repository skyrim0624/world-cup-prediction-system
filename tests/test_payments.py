import unittest

from fastapi.testclient import TestClient

from backend.payments import create_payment_order
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


if __name__ == "__main__":
    unittest.main()
