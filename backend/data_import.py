from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .data import WORLD_CUP_GROUPS


def validate_tournament_import_payload(payload: dict[str, Any]) -> dict[str, object]:
    teams = payload.get("teams")
    fixtures = payload.get("fixtures")
    if not isinstance(teams, list) or not isinstance(fixtures, list):
        raise ValueError("导入数据必须包含 teams 和 fixtures")
    if len(teams) != 48:
        raise ValueError("正式球队导入必须包含 48 支球队")
    if len(fixtures) != 72:
        raise ValueError("小组赛赛程导入必须包含 72 场比赛")

    team_keys = [team.get("key") for team in teams]
    team_codes = [team.get("code") for team in teams]
    if len(set(team_keys)) != 48:
        raise ValueError("球队 key 不能重复")
    if len(set(team_codes)) != 48:
        raise ValueError("球队 code 不能重复")

    known_teams = set(team_keys)
    groups = {group: [] for group in WORLD_CUP_GROUPS}
    for team in teams:
        group = team.get("group")
        if group not in groups:
            raise ValueError(f"未知小组: {group}")
        groups[group].append(team["key"])

    for group, group_teams in groups.items():
        if len(group_teams) != 4:
            raise ValueError(f"{group} 组必须有 4 支球队")

    seen_pairs: set[tuple[str, str]] = set()
    team_group = {team["key"]: team["group"] for team in teams}
    for fixture in fixtures:
        home = fixture.get("home")
        away = fixture.get("away")
        if home not in known_teams or away not in known_teams:
            raise ValueError(f"赛程包含未知球队: {home} vs {away}")
        if team_group[home] != team_group[away]:
            raise ValueError(f"小组赛不能跨组: {home} vs {away}")
        pair = tuple(sorted((home, away)))
        if pair in seen_pairs:
            raise ValueError(f"赛程重复: {home} vs {away}")
        seen_pairs.add(pair)
        if fixture.get("status") == "finished" and ("home_score" not in fixture or "away_score" not in fixture):
            raise ValueError(f"已完赛必须有比分: {home} vs {away}")
        if fixture.get("status") == "live" and ("home_score" not in fixture or "away_score" not in fixture):
            raise ValueError(f"进行中比赛必须有当前比分: {home} vs {away}")

    return {
        "source": payload.get("source", "unknown"),
        "teamCount": len(teams),
        "fixtureCount": len(fixtures),
        "groupCount": len(groups),
    }


def apply_tournament_data_import(data_dir: Path, backup_root: Path, payload: dict[str, Any]) -> dict[str, object]:
    summary = validate_tournament_import_payload(payload)
    teams_path = data_dir / "teams.json"
    fixtures_path = data_dir / "fixtures.json"
    backup_dir = backup_root / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    backup_dir.mkdir(parents=True, exist_ok=False)
    shutil.copy2(teams_path, backup_dir / "teams.json")
    shutil.copy2(fixtures_path, backup_dir / "fixtures.json")

    teams_path.write_text(json.dumps(payload["teams"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    fixtures_path.write_text(json.dumps(payload["fixtures"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        **summary,
        "backupDir": str(backup_dir),
    }
