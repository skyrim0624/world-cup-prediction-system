import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from backend.data_import import apply_tournament_data_import


def make_team(group: str, slot: int) -> dict[str, object]:
    key = f"{group.lower()}-{slot}"
    return {
        "key": key,
        "name": f"{group}组球队{slot}",
        "code": f"{group}{slot}",
        "group": group,
        "elo": 1800 - slot,
        "attack": 80,
        "defense": 80,
        "goalkeeper": 80,
        "path": 70,
        "squad": 80,
    }


def make_import_payload() -> dict[str, object]:
    groups = tuple("ABCDEFGHIJKL")
    teams = [make_team(group, slot) for group in groups for slot in range(1, 5)]
    fixtures = []
    for group in groups:
        group_keys = [team["key"] for team in teams if team["group"] == group]
        for index, home in enumerate(group_keys):
            for away in group_keys[index + 1 :]:
                fixtures.append(
                    {
                        "home": home,
                        "away": away,
                        "stage": f"小组赛 {group} 组",
                        "kickoff": "待定",
                        "status": "scheduled",
                    }
                )
    return {
        "source": "fifa-official-test",
        "retrievedAt": "2026-06-14T00:00:00Z",
        "teams": teams,
        "fixtures": fixtures,
    }


class TournamentDataImportTest(unittest.TestCase):
    def test_apply_tournament_data_import_writes_files_and_backup(self):
        payload = make_import_payload()
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir) / "data"
            backup_dir = Path(temp_dir) / "backups"
            data_dir.mkdir()
            (data_dir / "teams.json").write_text("[]", encoding="utf-8")
            (data_dir / "fixtures.json").write_text("[]", encoding="utf-8")

            result = apply_tournament_data_import(data_dir, backup_dir, payload)

            self.assertEqual(result["teamCount"], 48)
            self.assertEqual(result["fixtureCount"], 72)
            self.assertEqual(len(json.loads((data_dir / "teams.json").read_text(encoding="utf-8"))), 48)
            self.assertEqual(len(json.loads((data_dir / "fixtures.json").read_text(encoding="utf-8"))), 72)
            self.assertTrue(Path(result["backupDir"]).joinpath("teams.json").exists())
            self.assertTrue(Path(result["backupDir"]).joinpath("fixtures.json").exists())

    def test_apply_tournament_data_import_rejects_incomplete_team_set_without_writing(self):
        payload = make_import_payload()
        payload["teams"] = payload["teams"][:-1]
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir) / "data"
            backup_dir = Path(temp_dir) / "backups"
            data_dir.mkdir()
            original_teams = [{"key": "existing"}]
            (data_dir / "teams.json").write_text(json.dumps(original_teams), encoding="utf-8")
            (data_dir / "fixtures.json").write_text("[]", encoding="utf-8")

            with self.assertRaises(ValueError):
                apply_tournament_data_import(data_dir, backup_dir, payload)

            self.assertEqual(json.loads((data_dir / "teams.json").read_text(encoding="utf-8")), original_teams)
            self.assertFalse(backup_dir.exists())

    def test_apply_tournament_data_import_rejects_live_fixture_without_score(self):
        payload = make_import_payload()
        payload["fixtures"][0]["status"] = "live"

        with self.assertRaisesRegex(ValueError, "进行中比赛必须有当前比分"):
            apply_tournament_data_import(Path("/tmp/missing-data"), Path("/tmp/missing-backup"), payload)

    def test_import_tournament_data_script_runs_with_temp_paths(self):
        payload = make_import_payload()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_dir = root / "data"
            backup_dir = root / "backups"
            input_path = root / "official-import.json"
            data_dir.mkdir()
            input_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            (data_dir / "teams.json").write_text("[]", encoding="utf-8")
            (data_dir / "fixtures.json").write_text("[]", encoding="utf-8")

            result = subprocess.run(
                [
                    "python3",
                    "scripts/import_tournament_data.py",
                    "--input",
                    str(input_path),
                    "--data-dir",
                    str(data_dir),
                    "--backup-dir",
                    str(backup_dir),
                ],
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("已导入赛事数据", result.stdout)
            self.assertEqual(len(json.loads((data_dir / "teams.json").read_text(encoding="utf-8"))), 48)


if __name__ == "__main__":
    unittest.main()
