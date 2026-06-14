import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from backend.data_import import (
    apply_tournament_data_import,
    list_tournament_backups,
    restore_tournament_backup,
    validate_tournament_import_payload,
)


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
        payload["sourceUrl"] = "https://www.fifa.com/en/tournaments/mens/worldcup/canadamexicousa2026"
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
            provenance = json.loads((data_dir / "tournament-provenance.json").read_text(encoding="utf-8"))
            self.assertEqual(provenance["source"], "fifa-official-test")
            self.assertEqual(provenance["retrievedAt"], "2026-06-14T00:00:00Z")
            self.assertEqual(provenance["sourceUrl"], "https://www.fifa.com/en/tournaments/mens/worldcup/canadamexicousa2026")
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

    def test_apply_tournament_data_import_rejects_invalid_fixture_metadata(self):
        invalid_cases = [
            ("match_no", "31", "match_no 必须是数字"),
            ("city", 31, "city 必须是文本"),
            ("stadium", [], "stadium 必须是文本"),
        ]

        for field, value, message in invalid_cases:
            with self.subTest(field=field):
                payload = make_import_payload()
                payload["fixtures"][0][field] = value

                with self.assertRaisesRegex(ValueError, message):
                    validate_tournament_import_payload(payload)

    def test_apply_tournament_data_import_preserves_fixture_metadata(self):
        payload = make_import_payload()
        payload["fixtures"][0]["match_no"] = 31
        payload["fixtures"][0]["city"] = "Mexico City"
        payload["fixtures"][0]["stadium"] = "Estadio Azteca"

        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir) / "data"
            backup_dir = Path(temp_dir) / "backups"
            data_dir.mkdir()
            (data_dir / "teams.json").write_text("[]", encoding="utf-8")
            (data_dir / "fixtures.json").write_text("[]", encoding="utf-8")

            apply_tournament_data_import(data_dir, backup_dir, payload)

            fixtures = json.loads((data_dir / "fixtures.json").read_text(encoding="utf-8"))
            self.assertEqual(fixtures[0]["match_no"], 31)
            self.assertEqual(fixtures[0]["city"], "Mexico City")
            self.assertEqual(fixtures[0]["stadium"], "Estadio Azteca")

    def test_apply_tournament_data_import_writes_current_match_and_backup(self):
        payload = make_import_payload()
        payload["currentMatch"] = {"home": "a-1", "away": "a-2"}
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir) / "data"
            backup_dir = Path(temp_dir) / "backups"
            data_dir.mkdir()
            current_match = {"home": "old-home", "away": "old-away"}
            (data_dir / "teams.json").write_text("[]", encoding="utf-8")
            (data_dir / "fixtures.json").write_text("[]", encoding="utf-8")
            (data_dir / "current-match.json").write_text(json.dumps(current_match), encoding="utf-8")
            (data_dir / "tournament-provenance.json").write_text(json.dumps({"source": "old-source"}), encoding="utf-8")

            result = apply_tournament_data_import(data_dir, backup_dir, payload)

            self.assertEqual(json.loads((data_dir / "current-match.json").read_text(encoding="utf-8")), payload["currentMatch"])
            self.assertEqual(json.loads((Path(result["backupDir"]) / "current-match.json").read_text(encoding="utf-8")), current_match)
            self.assertEqual(json.loads((Path(result["backupDir"]) / "tournament-provenance.json").read_text(encoding="utf-8")), {"source": "old-source"})

    def test_apply_tournament_data_import_rejects_current_match_outside_new_fixtures(self):
        payload = make_import_payload()
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir) / "data"
            backup_dir = Path(temp_dir) / "backups"
            data_dir.mkdir()
            original_teams = [{"key": "existing"}]
            (data_dir / "teams.json").write_text(json.dumps(original_teams), encoding="utf-8")
            (data_dir / "fixtures.json").write_text("[]", encoding="utf-8")
            (data_dir / "current-match.json").write_text(json.dumps({"home": "legacy", "away": "other"}), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "当前主预测比赛不在导入赛程中"):
                apply_tournament_data_import(data_dir, backup_dir, payload)

            self.assertEqual(json.loads((data_dir / "teams.json").read_text(encoding="utf-8")), original_teams)
            self.assertFalse(backup_dir.exists())

    def test_restore_tournament_backup_restores_files_and_backs_up_current_state(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_dir = root / "data"
            backup_root = root / "backups"
            backup_id = "20260614T080000000000Z"
            backup_dir = backup_root / backup_id
            data_dir.mkdir()
            backup_dir.mkdir(parents=True)
            current_teams = [{"key": "current"}]
            current_fixtures = [{"home": "current", "away": "other"}]
            current_match = {"home": "current", "away": "other"}
            restored_teams = [{"key": "restored"}]
            restored_fixtures = [{"home": "restored", "away": "other"}]
            restored_match = {"home": "restored", "away": "other"}
            (data_dir / "teams.json").write_text(json.dumps(current_teams), encoding="utf-8")
            (data_dir / "fixtures.json").write_text(json.dumps(current_fixtures), encoding="utf-8")
            (data_dir / "current-match.json").write_text(json.dumps(current_match), encoding="utf-8")
            (backup_dir / "teams.json").write_text(json.dumps(restored_teams), encoding="utf-8")
            (backup_dir / "fixtures.json").write_text(json.dumps(restored_fixtures), encoding="utf-8")
            (backup_dir / "current-match.json").write_text(json.dumps(restored_match), encoding="utf-8")

            result = restore_tournament_backup(data_dir, backup_root, backup_id)

            rollback_backup = Path(result["currentBackupDir"])
            self.assertEqual(result["restoredBackupId"], backup_id)
            self.assertEqual(json.loads((data_dir / "teams.json").read_text(encoding="utf-8")), restored_teams)
            self.assertEqual(json.loads((data_dir / "fixtures.json").read_text(encoding="utf-8")), restored_fixtures)
            self.assertEqual(json.loads((data_dir / "current-match.json").read_text(encoding="utf-8")), restored_match)
            self.assertEqual(json.loads((rollback_backup / "teams.json").read_text(encoding="utf-8")), current_teams)
            self.assertEqual(json.loads((rollback_backup / "current-match.json").read_text(encoding="utf-8")), current_match)

    def test_restore_tournament_backup_rejects_path_traversal(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(ValueError):
                restore_tournament_backup(Path(temp_dir) / "data", Path(temp_dir) / "backups", "../outside")

    def test_list_tournament_backups_returns_recent_complete_backups(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            backup_root = Path(temp_dir) / "backups"
            older = backup_root / "20260614T070000000000Z"
            newer = backup_root / "20260614T080000000000Z"
            incomplete = backup_root / "20260614T090000000000Z"
            for backup_dir in (older, newer, incomplete):
                backup_dir.mkdir(parents=True)
                (backup_dir / "teams.json").write_text("[]", encoding="utf-8")
            (older / "fixtures.json").write_text("[]", encoding="utf-8")
            (newer / "fixtures.json").write_text("[]", encoding="utf-8")

            backups = list_tournament_backups(backup_root)

            self.assertEqual([item["backupId"] for item in backups], ["20260614T080000000000Z", "20260614T070000000000Z"])
            self.assertTrue(all(item["isComplete"] for item in backups))

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
