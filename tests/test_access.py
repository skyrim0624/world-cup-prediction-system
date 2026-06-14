import unittest

from backend.access import build_access_decision, build_access_policy


class AccessPolicyTest(unittest.TestCase):
    def test_single_match_product_unlocks_match_content_only(self):
        allowed = build_access_decision("single_match", "match_prediction", payment_configured=True)
        denied = build_access_decision("single_match", "tournament_probabilities", payment_configured=True)

        self.assertTrue(allowed["allowed"])
        self.assertEqual(allowed["reason"], "allowed")
        self.assertFalse(denied["allowed"])
        self.assertEqual(denied["reason"], "product_not_in_scope")
        self.assertEqual(denied["requiredProducts"], ["tournament_pass"])

    def test_payment_pending_blocks_access_decision(self):
        decision = build_access_decision("tournament_pass", "tournament_probabilities", payment_configured=False)

        self.assertFalse(decision["allowed"])
        self.assertEqual(decision["reason"], "payment_pending")

    def test_access_policy_lists_product_gates(self):
        policy = build_access_policy(payment_configured=False)
        content_keys = [item["contentKey"] for item in policy["content"]]

        self.assertIn("match_prediction", content_keys)
        self.assertIn("tournament_probabilities", content_keys)
        self.assertFalse(policy["paymentConfigured"])


if __name__ == "__main__":
    unittest.main()
