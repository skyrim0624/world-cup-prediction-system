import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from backend.snapshot import build_probability_movers, previous_snapshot_path_for, read_prediction_snapshot, write_prediction_snapshot


class PredictionSnapshotTest(unittest.TestCase):
    def test_write_prediction_snapshot_creates_json_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "latest.json"
            write_prediction_snapshot(output_path, simulation_count=1200)
            payload = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["modelMeta"]["simulationCount"], 1200)
            self.assertIn("snapshotMeta", payload)
            self.assertIn("dailyMovers", payload)
            self.assertEqual(payload["snapshotMeta"]["type"], "match-prediction")

    def test_read_prediction_snapshot_returns_payload_when_file_exists(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "latest.json"
            written = write_prediction_snapshot(output_path, simulation_count=1200)
            loaded = read_prediction_snapshot(output_path)
            self.assertEqual(loaded["updatedAt"], written["updatedAt"])
            self.assertEqual(loaded["modelMeta"]["changeBaseline"], "unadjusted_model")

    def test_read_prediction_snapshot_rejects_stale_payload_without_change_baseline(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "stale.json"
            output_path.write_text(
                json.dumps(
                    {
                        "updatedAt": "2026-06-14T00:00:00Z",
                        "modelMeta": {
                            "simulationCount": 1200,
                            "lockedResults": 3,
                            "dataset": {},
                            "events": {},
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            self.assertIsNone(read_prediction_snapshot(output_path))

    def test_read_prediction_snapshot_rejects_payload_without_daily_movers(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "missing-movers.json"
            payload = write_prediction_snapshot(output_path, simulation_count=1200)
            payload.pop("dailyMovers")
            output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

            self.assertIsNone(read_prediction_snapshot(output_path))

    def test_build_probability_movers_compares_current_to_previous_snapshot(self):
        previous = {
            "teams": [
                {"key": "brazil", "name": "巴西", "code": "BRA", "tournament": {"champion": 10.0}},
                {"key": "france", "name": "法国", "code": "FRA", "tournament": {"champion": 12.0}},
            ]
        }
        current = {
            "teams": [
                {"key": "brazil", "name": "巴西", "code": "BRA", "tournament": {"champion": 13.2}},
                {"key": "france", "name": "法国", "code": "FRA", "tournament": {"champion": 9.9}},
            ]
        }

        movers = build_probability_movers(current, previous)

        self.assertEqual(movers["baseline"], "previous_snapshot")
        self.assertEqual(movers["items"][0]["team"], "brazil")
        self.assertEqual(movers["items"][0]["change"], 3.2)
        self.assertEqual(movers["summary"]["largestDown"]["team"], "france")

    def test_write_prediction_snapshot_preserves_previous_snapshot_and_exposes_movers(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "latest.json"
            first = write_prediction_snapshot(output_path, simulation_count=1200)
            first["teams"][0]["tournament"]["champion"] = max(0, first["teams"][0]["tournament"]["champion"] - 2.0)
            output_path.write_text(json.dumps(first, ensure_ascii=False, indent=2), encoding="utf-8")

            second = write_prediction_snapshot(output_path, simulation_count=1200)
            previous_path = previous_snapshot_path_for(output_path)
            previous = read_prediction_snapshot(previous_path)

            self.assertTrue(previous_path.exists())
            self.assertIsNotNone(previous)
            self.assertEqual(second["dailyMovers"]["baseline"], "previous_snapshot")
            self.assertGreater(len(second["dailyMovers"]["items"]), 0)

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
