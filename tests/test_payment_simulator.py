import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]


class PaymentSimulatorTest(unittest.TestCase):
    def test_local_payment_simulator_covers_three_customer_payment_methods(self):
        result = subprocess.run(
            [sys.executable, "scripts/simulate_payment_flows.py", "--json"],
            cwd=ROOT_DIR,
            text=True,
            capture_output=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)

        self.assertTrue(payload["ok"])
        self.assertEqual(
            [item["provider"] for item in payload["flows"]],
            ["wechat_jsapi", "wechat_native", "alipay_qr"],
        )
        self.assertEqual({item["statusAfterSync"] for item in payload["flows"]}, {"paid"})
        self.assertEqual({item["accessAllowed"] for item in payload["flows"]}, {True})
        self.assertTrue(payload["flows"][0]["hasJsapiParams"])
        self.assertFalse(payload["flows"][0]["hasQrCode"])
        self.assertFalse(payload["flows"][1]["hasJsapiParams"])
        self.assertTrue(payload["flows"][1]["hasQrCode"])
        self.assertTrue(payload["flows"][2]["hasQrCode"])


if __name__ == "__main__":
    unittest.main()
