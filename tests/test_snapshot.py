import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from backend.snapshot import read_prediction_snapshot, write_prediction_snapshot


class PredictionSnapshotTest(unittest.TestCase):
    def test_write_prediction_snapshot_creates_json_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "latest.json"
            write_prediction_snapshot(output_path, simulation_count=1200)
            payload = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["modelMeta"]["simulationCount"], 1200)
            self.assertIn("snapshotMeta", payload)
            self.assertEqual(payload["snapshotMeta"]["type"], "match-prediction")

    def test_read_prediction_snapshot_returns_payload_when_file_exists(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "latest.json"
            written = write_prediction_snapshot(output_path, simulation_count=1200)
            loaded = read_prediction_snapshot(output_path)
            self.assertEqual(loaded["updatedAt"], written["updatedAt"])

    def test_read_prediction_snapshot_returns_none_when_missing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "missing.json"
            self.assertIsNone(read_prediction_snapshot(output_path))

    def test_update_snapshot_script_runs_from_project_root(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "latest.json"
            result = subprocess.run(
                [
                    "python3",
                    "scripts/update_prediction_snapshot.py",
                    "--simulations",
                    "1200",
                    "--output",
                    str(output_path),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(output_path.exists())


if __name__ == "__main__":
    unittest.main()
