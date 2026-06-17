import hashlib
import hmac
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

import backend.main as main_module
from backend.payments import (
    PAYMENT_ORDERS,
    build_order_access_decision,
    build_payment_config,
    create_payment_order,
    get_payment_order,
    handle_payment_notification,
    refresh_payment_order_status,
    update_payment_order_status,
)
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

    def test_payment_config_can_enable_local_simulation_mode(self):
        payload = build_payment_config(env={"WORLD_CUP_PAYMENT_SIMULATION": "1"})

        self.assertTrue(payload["ready"])
        self.assertTrue(payload["simulationMode"])
        self.assertEqual([provider["provider"] for provider in payload["providers"]], ["wechat_jsapi", "wechat_native", "alipay_qr"])
        self.assertTrue(all(provider["configured"] for provider in payload["providers"]))
        self.assertTrue(all(provider["missingConfig"] == [] for provider in payload["providers"]))

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

    def test_local_simulated_native_payment_order_auto_pays_on_status_sync(self):
        with TemporaryDirectory() as temp_dir:
            store_path = Path(temp_dir) / "payment-orders.json"
            env = {"WORLD_CUP_PAYMENT_SIMULATION": "1"}

            created = create_payment_order(
                "single_match",
                "wechat_native",
                metadata={"contentKey": "match_prediction", "matchKey": "netherlands-japan"},
                env=env,
                storage_path=store_path,
            )
            refreshed = refresh_payment_order_status(created["orderId"], env=env, storage_path=store_path)
            decision = build_order_access_decision(
                created["orderId"],
                "match_prediction",
                match_key="netherlands-japan",
                storage_path=store_path,
            )

        self.assertEqual(created["status"], "pending")
        self.assertEqual(created["missingConfig"], [])
        self.assertTrue(str(created["qrCodeUrl"]).startswith("data:image/svg+xml"))
        self.assertEqual(refreshed["status"], "paid")
        self.assertTrue(decision["allowed"])

    def test_local_simulated_jsapi_payment_order_returns_jsapi_params(self):
        with TemporaryDirectory() as temp_dir:
            store_path = Path(temp_dir) / "payment-orders.json"
            env = {"WORLD_CUP_PAYMENT_SIMULATION": "1"}

            created = create_payment_order("single_match", "wechat_jsapi", env=env, storage_path=store_path)
            refreshed = refresh_payment_order_status(created["orderId"], env=env, storage_path=store_path)

        self.assertEqual(created["status"], "pending")
        self.assertIn("jsapiParams", created)
        self.assertIn("package", created["jsapiParams"])
        self.assertEqual(refreshed["status"], "paid")

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

    def test_payment_order_survives_unwritable_json_store(self):
        with TemporaryDirectory() as temp_dir:
            blocked_parent = Path(temp_dir) / "payment-orders-parent"
            blocked_parent.write_text("not a directory", encoding="utf-8")
            storage_path = blocked_parent / "payment-orders.json"

            created = create_payment_order("single_match", "wechat_native", storage_path=storage_path)
            loaded = get_payment_order(created["orderId"], storage_path=storage_path)

        self.assertEqual(loaded["orderId"], created["orderId"])
        self.assertEqual(loaded["status"], "provider_config_required")

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

    def test_configured_native_order_calls_customer_create_interface_and_stores_qr(self):
        captured = {}

        def fake_requester(url, payload, headers, method="POST"):
            captured["url"] = url
            captured["payload"] = payload
            captured["headers"] = headers
            captured["method"] = method
            return {
                "status": "pending",
                "qrCodeUrl": "https://pay.example/qr/wechat-native.png",
                "providerOrderId": "wx_provider_123",
            }

        order = create_payment_order(
            "single_match",
            "wechat_native",
            metadata={
                "contentKey": "match_prediction",
                "matchKey": "spain-cape-verde",
                "homeTeam": "spain",
                "awayTeam": "cape-verde",
                "homeName": "西班牙",
                "awayName": "佛得角",
            },
            env={
                "CUSTOMER_WECHAT_NATIVE_PAY_CREATE_URL": "https://customer.example/pay/wechat/create",
                "CUSTOMER_WECHAT_NATIVE_PAY_STATUS_URL": "https://customer.example/pay/wechat/status",
                "CUSTOMER_WECHAT_NATIVE_PAY_NOTIFY_SECRET": "secret",
                "CUSTOMER_WECHAT_NATIVE_PAY_AUTH_TOKEN": "token-123",
                "WORLD_CUP_PUBLIC_API_BASE_URL": "https://api.example.com",
            },
            payment_requester=fake_requester,
        )

        self.assertEqual(captured["url"], "https://customer.example/pay/wechat/create")
        self.assertEqual(captured["method"], "POST")
        self.assertEqual(captured["headers"]["Authorization"], "Bearer token-123")
        self.assertEqual(captured["payload"]["outTradeNo"], order["orderId"])
        self.assertEqual(captured["payload"]["amountCents"], 100)
        self.assertEqual(captured["payload"]["paymentMethod"], "native")
        self.assertEqual(captured["payload"]["contentKey"], "match_prediction")
        self.assertEqual(captured["payload"]["matchKey"], "spain-cape-verde")
        self.assertEqual(captured["payload"]["homeName"], "西班牙")
        self.assertEqual(captured["payload"]["awayName"], "佛得角")
        self.assertEqual(captured["payload"]["notifyUrl"], "https://api.example.com/api/app-payment/wechat/notify")
        self.assertEqual(order["status"], "pending")
        self.assertEqual(order["qrCodeUrl"], "https://pay.example/qr/wechat-native.png")
        self.assertEqual(order["providerOrderId"], "wx_provider_123")
        self.assertEqual(order["nextAction"], "等待用户扫码支付。")

    def test_configured_native_notify_url_overrides_default_worker_callback(self):
        captured = {}

        def fake_requester(url, payload, headers, method="POST"):
            captured["payload"] = payload
            return {"status": "pending", "qrCodeUrl": "https://pay.example/qr.png"}

        create_payment_order(
            "single_match",
            "wechat_native",
            env={
                "CUSTOMER_WECHAT_NATIVE_PAY_CREATE_URL": "https://customer.example/pay/wechat/create",
                "CUSTOMER_WECHAT_NATIVE_PAY_STATUS_URL": "https://customer.example/pay/wechat/status",
                "CUSTOMER_WECHAT_NATIVE_PAY_NOTIFY_SECRET": "secret",
                "CUSTOMER_WECHAT_NATIVE_PAY_NOTIFY_URL": "https://zhugejunshi.com/api/app-payment/wechat/notify",
            },
            payment_requester=fake_requester,
        )

        self.assertEqual(captured["payload"]["notifyUrl"], "https://zhugejunshi.com/api/app-payment/wechat/notify")

    def test_customer_create_interface_accepts_nested_data_response(self):
        order = create_payment_order(
            "single_match",
            "wechat_native",
            env={
                "CUSTOMER_WECHAT_NATIVE_PAY_CREATE_URL": "https://customer.example/pay/wechat/create",
                "CUSTOMER_WECHAT_NATIVE_PAY_STATUS_URL": "https://customer.example/pay/wechat/status",
                "CUSTOMER_WECHAT_NATIVE_PAY_NOTIFY_SECRET": "secret",
            },
            payment_requester=lambda url, payload, headers, method="POST": {
                "code": 0,
                "data": {
                    "status": "pending",
                    "code_url": "weixin://wxpay/bizpayurl?pr=test",
                    "prepay_id": "wx_prepay_nested",
                },
            },
        )

        self.assertEqual(order["status"], "pending")
        self.assertEqual(order["qrCodeUrl"], "weixin://wxpay/bizpayurl?pr=test")
        self.assertEqual(order["providerOrderId"], "wx_prepay_nested")

    def test_configured_jsapi_order_persists_jsapi_params(self):
        captured = {}

        def fake_requester(url, payload, headers, method="POST"):
            captured["payload"] = payload
            return {
                "status": "pending",
                "jsapiParams": {
                    "appId": "wx-app",
                    "timeStamp": "1781500000",
                    "nonceStr": "nonce",
                    "package": "prepay_id=wx-prepay",
                    "signType": "RSA",
                    "paySign": "signature",
                },
                "prepayId": "wx-prepay",
            }

        order = create_payment_order(
            "single_match",
            "wechat_jsapi",
            metadata={"wechatOpenId": "openid-123"},
            env={
                "CUSTOMER_WECHAT_JSAPI_PAY_CREATE_URL": "https://customer.example/pay/wechat-jsapi/create",
                "CUSTOMER_WECHAT_JSAPI_PAY_STATUS_URL": "https://customer.example/pay/wechat-jsapi/status",
                "CUSTOMER_WECHAT_JSAPI_PAY_NOTIFY_SECRET": "secret",
                "WORLD_CUP_PUBLIC_API_BASE_URL": "https://api.example.com",
            },
            payment_requester=fake_requester,
        )

        self.assertEqual(order["status"], "pending")
        self.assertEqual(order["jsapiParams"]["package"], "prepay_id=wx-prepay")
        self.assertEqual(order["providerOrderId"], "wx-prepay")
        self.assertEqual(captured["payload"]["notifyUrl"], "https://api.example.com/api/payments/notify/wechat_jsapi")

    def test_refresh_payment_order_status_queries_customer_status_and_marks_paid(self):
        with TemporaryDirectory() as temp_dir:
            store_path = Path(temp_dir) / "payment-orders.json"
            env = {
                "CUSTOMER_WECHAT_NATIVE_PAY_CREATE_URL": "https://customer.example/pay/wechat/create",
                "CUSTOMER_WECHAT_NATIVE_PAY_STATUS_URL": "https://customer.example/pay/wechat/status",
                "CUSTOMER_WECHAT_NATIVE_PAY_NOTIFY_SECRET": "secret",
            }

            created = create_payment_order(
                "single_match",
                "wechat_native",
                env=env,
                storage_path=store_path,
                payment_requester=lambda url, payload, headers, method="POST": {"status": "pending", "qrCodeUrl": "https://pay.example/qr.png"},
            )

            refreshed = refresh_payment_order_status(
                created["orderId"],
                env=env,
                storage_path=store_path,
                payment_requester=lambda url, payload, headers, method="POST": {"status": "SUCCESS", "transactionId": "wx_tx_123"},
            )

        self.assertEqual(refreshed["status"], "paid")
        self.assertEqual(refreshed["transactionId"], "wx_tx_123")

    def test_alipay_trade_success_status_normalizes_to_paid(self):
        with TemporaryDirectory() as temp_dir:
            store_path = Path(temp_dir) / "payment-orders.json"
            env = {
                "CUSTOMER_ALIPAY_QR_PAY_CREATE_URL": "https://customer.example/pay/alipay/create",
                "CUSTOMER_ALIPAY_QR_PAY_STATUS_URL": "https://customer.example/pay/alipay/status",
                "CUSTOMER_ALIPAY_QR_PAY_NOTIFY_SECRET": "secret",
            }

            created = create_payment_order(
                "single_match",
                "alipay_qr",
                env=env,
                storage_path=store_path,
                payment_requester=lambda url, payload, headers, method="POST": {"status": "WAIT_BUYER_PAY", "qrCodeUrl": "https://pay.example/alipay.png"},
            )

            refreshed = refresh_payment_order_status(
                created["orderId"],
                env=env,
                storage_path=store_path,
                payment_requester=lambda url, payload, headers, method="POST": {"trade_status": "TRADE_SUCCESS", "trade_no": "ali_trade_123"},
            )

        self.assertEqual(refreshed["status"], "paid")
        self.assertEqual(refreshed["transactionId"], "ali_trade_123")

    def test_payment_notification_marks_order_paid_after_valid_signature(self):
        with TemporaryDirectory() as temp_dir:
            store_path = Path(temp_dir) / "payment-orders.json"
            created = create_payment_order("single_match", "wechat", storage_path=store_path)
            body = json.dumps({"orderId": created["orderId"], "status": "paid", "transactionId": "wx_tx_notify"}, separators=(",", ":")).encode("utf-8")
            signature = hmac.new(b"notify-secret", body, hashlib.sha256).hexdigest()

            result = handle_payment_notification(
                "wechat_native",
                body,
                {"x-payment-signature": signature},
                env={"CUSTOMER_WECHAT_NATIVE_PAY_NOTIFY_SECRET": "notify-secret"},
                storage_path=store_path,
            )

            updated = get_payment_order(created["orderId"], storage_path=store_path)

        self.assertTrue(result["ok"])
        self.assertEqual(updated["status"], "paid")
        self.assertEqual(updated["transactionId"], "wx_tx_notify")

    def test_payment_notification_rejects_invalid_signature(self):
        with TemporaryDirectory() as temp_dir:
            store_path = Path(temp_dir) / "payment-orders.json"
            created = create_payment_order("single_match", "wechat", storage_path=store_path)
            body = json.dumps({"orderId": created["orderId"], "status": "paid"}, separators=(",", ":")).encode("utf-8")

            result = handle_payment_notification(
                "wechat_native",
                body,
                {"x-payment-signature": "bad-signature"},
                env={"CUSTOMER_WECHAT_NATIVE_PAY_NOTIFY_SECRET": "notify-secret"},
                storage_path=store_path,
            )

            updated = get_payment_order(created["orderId"], storage_path=store_path)

        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], "invalid_signature")
        self.assertNotEqual(updated["status"], "paid")

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

    def test_paid_tournament_pass_unlocks_any_single_match_prediction(self):
        with TemporaryDirectory() as temp_dir:
            store_path = Path(temp_dir) / "payment-orders.json"
            created = create_payment_order(
                "tournament_pass",
                "wechat",
                metadata={"contentKey": "tournament_probabilities", "matchKey": "spain-cape-verde"},
                storage_path=store_path,
            )
            update_payment_order_status(created["orderId"], "paid", storage_path=store_path)

            match_allowed = build_order_access_decision(created["orderId"], "match_prediction", match_key="brazil-argentina", storage_path=store_path)
            tournament_allowed = build_order_access_decision(created["orderId"], "tournament_probabilities", storage_path=store_path)

        self.assertTrue(match_allowed["allowed"])
        self.assertEqual(match_allowed["reason"], "allowed")
        self.assertTrue(tournament_allowed["allowed"])
        self.assertEqual(tournament_allowed["reason"], "allowed")

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
                        "wechatOpenId": "openid-from-front",
                    },
                ).json()
                PAYMENT_ORDERS.clear()

                response = client.get(f"/api/payments/orders/{created['orderId']}")
            finally:
                main_module.payment_orders_path = previous_path

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["orderId"], created["orderId"])
        self.assertEqual(response.json()["metadata"]["matchKey"], "netherlands-japan")
        self.assertEqual(response.json()["metadata"]["wechatOpenId"], "openid-from-front")

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

    def test_payment_notify_api_updates_order_after_signature_check(self):
        client = TestClient(app)
        with TemporaryDirectory() as temp_dir:
            store_path = Path(temp_dir) / "payment-orders.json"
            previous_path = main_module.payment_orders_path
            main_module.payment_orders_path = store_path
            try:
                created = create_payment_order("single_match", "wechat", storage_path=store_path)
                body = json.dumps({"orderId": created["orderId"], "status": "SUCCESS", "transactionId": "wx_tx_api"}, separators=(",", ":")).encode("utf-8")
                signature = hmac.new(b"notify-secret", body, hashlib.sha256).hexdigest()

                previous_secret = main_module.os.environ.get("CUSTOMER_WECHAT_NATIVE_PAY_NOTIFY_SECRET")
                main_module.os.environ["CUSTOMER_WECHAT_NATIVE_PAY_NOTIFY_SECRET"] = "notify-secret"
                try:
                    response = client.post(
                        "/api/payments/notify/wechat_native",
                        content=body,
                        headers={"X-Payment-Signature": signature, "Content-Type": "application/json"},
                    )
                finally:
                    if previous_secret is None:
                        main_module.os.environ.pop("CUSTOMER_WECHAT_NATIVE_PAY_NOTIFY_SECRET", None)
                    else:
                        main_module.os.environ["CUSTOMER_WECHAT_NATIVE_PAY_NOTIFY_SECRET"] = previous_secret
            finally:
                main_module.payment_orders_path = previous_path

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "paid")

    def test_native_legacy_notify_api_updates_order_after_signature_check(self):
        client = TestClient(app)
        with TemporaryDirectory() as temp_dir:
            store_path = Path(temp_dir) / "payment-orders.json"
            previous_path = main_module.payment_orders_path
            main_module.payment_orders_path = store_path
            try:
                created = create_payment_order("single_match", "wechat", storage_path=store_path)
                body = json.dumps({"orderId": created["orderId"], "status": "SUCCESS", "transactionId": "wx_tx_legacy"}, separators=(",", ":")).encode("utf-8")
                signature = hmac.new(b"notify-secret", body, hashlib.sha256).hexdigest()

                previous_secret = main_module.os.environ.get("CUSTOMER_WECHAT_NATIVE_PAY_NOTIFY_SECRET")
                main_module.os.environ["CUSTOMER_WECHAT_NATIVE_PAY_NOTIFY_SECRET"] = "notify-secret"
                try:
                    response = client.post(
                        "/api/app-payment/wechat/notify",
                        content=body,
                        headers={"X-Payment-Signature": signature, "Content-Type": "application/json"},
                    )
                finally:
                    if previous_secret is None:
                        main_module.os.environ.pop("CUSTOMER_WECHAT_NATIVE_PAY_NOTIFY_SECRET", None)
                    else:
                        main_module.os.environ["CUSTOMER_WECHAT_NATIVE_PAY_NOTIFY_SECRET"] = previous_secret
            finally:
                main_module.payment_orders_path = previous_path

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "paid")

    def test_payment_notify_api_rejects_bad_signature(self):
        client = TestClient(app)
        with TemporaryDirectory() as temp_dir:
            store_path = Path(temp_dir) / "payment-orders.json"
            previous_path = main_module.payment_orders_path
            main_module.payment_orders_path = store_path
            try:
                created = create_payment_order("single_match", "wechat", storage_path=store_path)
                body = json.dumps({"orderId": created["orderId"], "status": "SUCCESS"}, separators=(",", ":")).encode("utf-8")
                previous_secret = main_module.os.environ.get("CUSTOMER_WECHAT_NATIVE_PAY_NOTIFY_SECRET")
                main_module.os.environ["CUSTOMER_WECHAT_NATIVE_PAY_NOTIFY_SECRET"] = "notify-secret"
                try:
                    response = client.post(
                        "/api/payments/notify/wechat_native",
                        content=body,
                        headers={"X-Payment-Signature": "bad", "Content-Type": "application/json"},
                    )
                finally:
                    if previous_secret is None:
                        main_module.os.environ.pop("CUSTOMER_WECHAT_NATIVE_PAY_NOTIFY_SECRET", None)
                    else:
                        main_module.os.environ["CUSTOMER_WECHAT_NATIVE_PAY_NOTIFY_SECRET"] = previous_secret
            finally:
                main_module.payment_orders_path = previous_path

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "invalid_signature")


if __name__ == "__main__":
    unittest.main()
