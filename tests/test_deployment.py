from pathlib import Path
import unittest


class DeploymentAutomationTest(unittest.TestCase):
    def test_daily_update_github_action_runs_on_schedule(self):
        workflow = Path(".github/workflows/daily-update.yml").read_text(encoding="utf-8")

        self.assertIn('cron: "*/30 * * * *"', workflow)
        self.assertIn("npm run validate:data", workflow)
        self.assertIn("npm run daily:update", workflow)
        self.assertIn("npm run daily:check", workflow)
        self.assertIn("npm run deploy:api", workflow)
        self.assertIn("npm run deploy:web", workflow)

    def test_cloudflare_api_deploy_packages_model_quality_report(self):
        script = Path("scripts/deploy-cloudflare-api.sh").read_text(encoding="utf-8")

        self.assertIn("reports/model-quality-report.json", script)
        self.assertIn("python_modules/reports", script)


if __name__ == "__main__":
    unittest.main()
