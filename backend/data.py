from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DATA_DIR = Path(__file__).with_name("data_files")


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
    return profiles


def load_fixtures(team_profiles: dict[str, TeamProfile]) -> list[Fixture]:
    rows = read_json_file("fixtures.json")
    fixtures = [Fixture(**row) for row in rows]
    known_teams = set(team_profiles)
    for fixture in fixtures:
        if fixture.home not in known_teams or fixture.away not in known_teams:
            raise ValueError(f"赛程包含未知球队: {fixture.home} vs {fixture.away}")
        if fixture.status == "finished" and (fixture.home_score is None or fixture.away_score is None):
            raise ValueError(f"已完赛必须有比分: {fixture.home} vs {fixture.away}")
    return fixtures


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


def load_current_match() -> tuple[str, str]:
    row = read_json_file("current-match.json")
    return row["home"], row["away"]


TEAM_PROFILES = load_team_profiles()
FIXTURES = load_fixtures(TEAM_PROFILES)
EVENTS = load_events(TEAM_PROFILES)
SOURCE_WEIGHTS = load_source_weights()
CURRENT_MATCH = load_current_match()

DATASET_META = {
    "source": "local-json",
    "teamCount": len(TEAM_PROFILES),
    "fixtureCount": len(FIXTURES),
    "eventCount": len(EVENTS),
}
