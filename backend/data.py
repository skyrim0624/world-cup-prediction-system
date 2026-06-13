from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DATA_DIR = Path(__file__).with_name("data_files")
WORLD_CUP_GROUPS = tuple("ABCDEFGHIJKL")


@dataclass(frozen=True)
class TeamProfile:
    key: str
    name: str
    code: str
    group: str
    elo: int
    attack: int
    defense: int
    goalkeeper: int
    path: int
    squad: int


@dataclass(frozen=True)
class Fixture:
    home: str
    away: str
    stage: str
    kickoff: str
    status: str
    home_score: int | None = None
    away_score: int | None = None


@dataclass(frozen=True)
class TeamEvent:
    title: str
    detail: str
    team: str | None
    source_level: str
    factor: str
    direction: int
    strength: float
    time: str


def read_json_file(name: str) -> Any:
    with (DATA_DIR / name).open(encoding="utf-8") as file:
        return json.load(file)


def load_team_profiles() -> dict[str, TeamProfile]:
    rows = read_json_file("teams.json")
    profiles = {row["key"]: TeamProfile(**row) for row in rows}
    if len(profiles) != len(rows):
        raise ValueError("球队 key 不能重复")
    return complete_world_cup_slots(profiles)


def complete_world_cup_slots(profiles: dict[str, TeamProfile]) -> dict[str, TeamProfile]:
    completed = dict(profiles)
    for group_index, group in enumerate(WORLD_CUP_GROUPS):
        group_teams = [team for team in completed.values() if team.group == group]
        if len(group_teams) > 4:
            raise ValueError(f"{group} 组球队不能超过 4 支")
        for slot in range(len(group_teams) + 1, 5):
            key = f"slot-{group.lower()}{slot}"
            completed[key] = TeamProfile(
                key=key,
                name=f"{group}组第{slot}档球队",
                code=f"{group}{slot}",
                group=group,
                elo=1775 - group_index * 4 - slot * 7,
                attack=78 - min(group_index // 3, 4),
                defense=77 - min(group_index // 4, 3),
                goalkeeper=77,
                path=64 - min(group_index // 3, 4),
                squad=76,
            )
    return completed


def load_fixtures(team_profiles: dict[str, TeamProfile]) -> list[Fixture]:
    rows = read_json_file("fixtures.json")
    fixtures = [Fixture(**row) for row in rows]
    known_teams = set(team_profiles)
    for fixture in fixtures:
        if fixture.home not in known_teams or fixture.away not in known_teams:
            raise ValueError(f"赛程包含未知球队: {fixture.home} vs {fixture.away}")
        if fixture.status == "finished" and (fixture.home_score is None or fixture.away_score is None):
            raise ValueError(f"已完赛必须有比分: {fixture.home} vs {fixture.away}")
    return complete_group_fixtures(fixtures, team_profiles)


def complete_group_fixtures(fixtures: list[Fixture], team_profiles: dict[str, TeamProfile]) -> list[Fixture]:
    completed = list(fixtures)
    existing_pairs = {tuple(sorted((fixture.home, fixture.away))) for fixture in completed}
    for group in WORLD_CUP_GROUPS:
        group_team_keys = [team.key for team in team_profiles.values() if team.group == group]
        for index, home in enumerate(group_team_keys):
            for away in group_team_keys[index + 1 :]:
                pair = tuple(sorted((home, away)))
                if pair in existing_pairs:
                    continue
                completed.append(Fixture(home, away, f"小组赛 {group} 组", "待定", "scheduled"))
                existing_pairs.add(pair)
    return completed


def load_events(team_profiles: dict[str, TeamProfile]) -> list[TeamEvent]:
    rows = read_json_file("events.json")
    events = [TeamEvent(**row) for row in rows]
    known_teams = set(team_profiles)
    for event in events:
        if event.team is not None and event.team not in known_teams:
            raise ValueError(f"事件包含未知球队: {event.team}")
    return events


def load_source_weights() -> dict[str, float]:
    weights = read_json_file("source-weights.json")
    return {level: float(value) for level, value in weights.items()}


def load_third_place_combinations() -> dict[str, dict[str, str]]:
    data = read_json_file("third-place-combinations.json")
    combinations = data["combinations"]
    if len(combinations) != 495:
        raise ValueError("小组第三组合表必须包含 495 种组合")
    return combinations


def load_current_match() -> tuple[str, str]:
    row = read_json_file("current-match.json")
    return row["home"], row["away"]


TEAM_PROFILES = load_team_profiles()
FIXTURES = load_fixtures(TEAM_PROFILES)
EVENTS = load_events(TEAM_PROFILES)
SOURCE_WEIGHTS = load_source_weights()
THIRD_PLACE_COMBINATIONS = load_third_place_combinations()
CURRENT_MATCH = load_current_match()

DATASET_META = {
    "source": "local-json",
    "teamCount": len(TEAM_PROFILES),
    "groupCount": len(WORLD_CUP_GROUPS),
    "fixtureCount": len(FIXTURES),
    "eventCount": len(EVENTS),
    "placeholderSlots": len([team for team in TEAM_PROFILES.values() if team.key.startswith("slot-")]),
}
