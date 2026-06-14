from pathlib import Path
import unittest


class FrontendContractTest(unittest.TestCase):
    def test_homepage_renders_paid_access_boundary(self):
        app_source = Path("src/App.tsx").read_text(encoding="utf-8")
        self.assertIn("/api/access-options", app_source)
        self.assertIn("付费解锁", app_source)
        self.assertIn("AccessPanel", app_source)


if __name__ == "__main__":
    unittest.main()
