import subprocess
import unittest


class PredictionDataValidationTest(unittest.TestCase):
    def test_data_validation_script_runs(self):
        result = subprocess.run(
            ["python3", "scripts/validate_prediction_data.py"],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("数据校验通过", result.stdout)


if __name__ == "__main__":
    unittest.main()
