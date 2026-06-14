import os
import unittest

from backend.admin_security import resolve_admin_token


class ScopeEnv:
    WORLD_CUP_ADMIN_TOKEN = "scope-secret"


class RequestStub:
    scope = {"env": ScopeEnv()}


class AdminSecurityTest(unittest.TestCase):
    def test_resolve_admin_token_reads_cloudflare_scope_env_and_syncs_os_environ(self):
        previous_token = os.environ.get("WORLD_CUP_ADMIN_TOKEN")
        os.environ.pop("WORLD_CUP_ADMIN_TOKEN", None)
        try:
            token = resolve_admin_token(RequestStub())
        finally:
            synced_token = os.environ.get("WORLD_CUP_ADMIN_TOKEN")
            if previous_token is None:
                os.environ.pop("WORLD_CUP_ADMIN_TOKEN", None)
            else:
                os.environ["WORLD_CUP_ADMIN_TOKEN"] = previous_token

        self.assertEqual(token, "scope-secret")
        self.assertEqual(synced_token, "scope-secret")


if __name__ == "__main__":
    unittest.main()
