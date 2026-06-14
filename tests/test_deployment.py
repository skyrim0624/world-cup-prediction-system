from pathlib import Path
import unittest


class DeploymentAutomationTest(unittest.TestCase):
    def test_daily_update_github_action_runs_on_schedule(self):
        workflow = Path(".github/workflows/daily-update.yml").read_text(encoding="utf-8")

        self.assertIn("cron:", workflow)
        self.assertIn("npm run validate:data", workflow)
        self.assertIn("npm run daily:update", workflow)
        self.assertIn("npm run daily:check", workflow)


if __name__ == "__main__":
    unittest.main()
