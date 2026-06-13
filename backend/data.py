from __future__ import annotations

from dataclasses import dataclass


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


TEAM_PROFILES: dict[str, TeamProfile] = {
    "brazil": TeamProfile("brazil", "巴西", "BRA", "E", 1884, 90, 82, 85, 76, 84),
    "argentina": TeamProfile("argentina", "阿根廷", "ARG", "E", 1856, 87, 81, 83, 72, 82),
    "spain": TeamProfile("spain", "西班牙", "ESP", "E", 1868, 88, 86, 84, 79, 87),
    "france": TeamProfile("france", "法国", "FRA", "E", 1872, 89, 87, 86, 74, 89),
}


FIXTURES: list[Fixture] = [
    Fixture("spain", "france", "小组赛 E 组", "6月12日 08:00", "finished", 2, 1),
    Fixture("brazil", "spain", "小组赛 E 组", "6月13日 08:00", "finished", 1, 1),
    Fixture("argentina", "france", "小组赛 E 组", "6月14日 08:00", "finished", 2, 0),
    Fixture("brazil", "argentina", "小组赛 E 组", "6月15日 08:00", "scheduled"),
    Fixture("spain", "argentina", "小组赛 E 组", "6月18日 08:00", "scheduled"),
    Fixture("brazil", "france", "小组赛 E 组", "6月18日 11:00", "scheduled"),
]


CURRENT_MATCH = ("brazil", "argentina")


EVENTS: list[TeamEvent] = [
    TeamEvent(
        "官方名单",
        "两队暂无新增停赛，核心阵容可用",
        None,
        "S",
        "squad",
        1,
        0.01,
        "1 小时前",
    ),
    TeamEvent(
        "训练信息",
        "巴西边路主力单独训练，出场仍待确认",
        "brazil",
        "B",
        "attack",
        -1,
        0.035,
        "3 小时前",
    ),
    TeamEvent(
        "社媒传闻",
        "未证实更衣室消息，不改变概率",
        "argentina",
        "D",
        "squad",
        -1,
        0.06,
        "5 小时前",
    ),
]


SOURCE_WEIGHTS = {
    "S": 1.0,
    "A": 0.7,
    "B": 0.4,
    "C": 0.2,
    "D": 0.0,
}
