from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DATA_DIR = Path(__file__).with_name("data_files")
WORLD_CUP_GROUPS = tuple("ABCDEFGHIJKL")
TOURNAMENT_PROVENANCE_FILE = "tournament-provenance.json"


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
    match_no: int | None = None
    city: str | None = None
    stadium: str | None = None


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
    source: str = "manual"
    url: str | None = None
    status: str = "confirmed"
    action: str = "apply"
    id: str | None = None


@dataclass(frozen=True)
class NewsSource:
    key: str
    name: str
    source_level: str
    url: str


@dataclass(frozen=True)
class RawNewsItem:
    id: str
    title: str
    summary: str
    source: str
    team: str | None
    status: str
    published_at: str
    url: str
    category: str | None = None
    factor: str | None = None
    direction: int | None = None
    confidence: float | None = None
    players: list[str] | None = None
    kind: str | None = None
    sourceRegistryId: str | None = None


@dataclass(frozen=True)
class RuntimeDataset:
    team_profiles: dict[str, TeamProfile]
    fixtures: list[Fixture]
    source_weights: dict[str, float]
    news_sources: dict[str, NewsSource]
    raw_news_items: list[RawNewsItem]
    manual_events: list[TeamEvent]
    events: list[TeamEvent]
    third_place_combinations: dict[str, dict[str, str]]
    current_match: tuple[str, str]
    dataset_meta: dict[str, object]


def read_json_file(name: str) -> Any:
    with (DATA_DIR / name).open(encoding="utf-8") as file:
        return json.load(file)


def load_team_profiles(path: Path | None = None) -> dict[str, TeamProfile]:
    if path is None:
        rows = read_json_file("teams.json")
    else:
        rows = json.loads(path.read_text(encoding="utf-8"))
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


def load_fixtures(team_profiles: dict[str, TeamProfile], path: Path | None = None) -> list[Fixture]:
    if path is None:
        rows = read_json_file("fixtures.json")
    else:
        rows = json.loads(path.read_text(encoding="utf-8"))
    fixtures = [Fixture(**row) for row in rows]
    known_teams = set(team_profiles)
    for fixture in fixtures:
        if fixture.home not in known_teams or fixture.away not in known_teams:
            raise ValueError(f"赛程包含未知球队: {fixture.home} vs {fixture.away}")
        if fixture.status == "finished" and (fixture.home_score is None or fixture.away_score is None):
            raise ValueError(f"已完赛必须有比分: {fixture.home} vs {fixture.away}")
        if fixture.status == "live" and (fixture.home_score is None or fixture.away_score is None):
            raise ValueError(f"进行中比赛必须有当前比分: {fixture.home} vs {fixture.away}")
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


def load_events(team_profiles: dict[str, TeamProfile], drop_unknown_teams: bool = False) -> list[TeamEvent]:
    rows = read_json_file("events.json")
    events = [TeamEvent(**row) for row in rows]
    known_teams = set(team_profiles)
    compatible_events = []
    for event in events:
        if event.team is not None and event.team not in known_teams:
            if drop_unknown_teams:
                continue
            raise ValueError(f"事件包含未知球队: {event.team}")
        compatible_events.append(event)
    return compatible_events


def load_source_weights() -> dict[str, float]:
    weights = read_json_file("source-weights.json")
    return {level: float(value) for level, value in weights.items()}


def load_news_sources(source_weights: dict[str, float]) -> dict[str, NewsSource]:
    rows = read_json_file("news-sources.json")
    sources = {row["key"]: NewsSource(**row) for row in rows}
    if len(sources) != len(rows):
        raise ValueError("新闻来源 key 不能重复")
    for source in sources.values():
        if source.source_level not in source_weights:
            raise ValueError(f"新闻来源等级未知: {source.source_level}")
    return sources


def load_raw_news_items(
    team_profiles: dict[str, TeamProfile],
    news_sources: dict[str, NewsSource],
    path: Path | None = None,
    drop_unknown_teams: bool = False,
) -> list[RawNewsItem]:
    if path is None:
        rows = read_json_file("raw-news.json")
    else:
        rows = json.loads(path.read_text(encoding="utf-8"))
    items = [RawNewsItem(**row) for row in rows]
    known_ids = {item.id for item in items}
    if len(known_ids) != len(items):
        raise ValueError("原始新闻 id 不能重复")
    known_teams = set(team_profiles)
    compatible_items = []
    for item in items:
        if item.source not in news_sources:
            raise ValueError(f"原始新闻包含未知来源: {item.source}")
        if item.team is not None and item.team not in known_teams:
            if drop_unknown_teams:
                continue
            raise ValueError(f"原始新闻包含未知球队: {item.team}")
        compatible_items.append(item)
    return compatible_items


def infer_event_factor(text: str) -> str:
    if any(keyword in text for keyword in ("门将", "扑救")):
        return "goalkeeper"
    if any(keyword in text for keyword in ("后卫", "中卫", "防线", "防守")):
        return "defense"
    if any(keyword in text for keyword in ("赛程", "旅程", "天气", "高温", "恢复")):
        return "path"
    if any(keyword in text for keyword in ("前锋", "边锋", "边路", "进攻", "射手")):
        return "attack"
    return "squad"


def infer_event_direction(text: str) -> int:
    if any(keyword in text for keyword in ("恢复合练", "复出", "确认可用", "回归", "首发")):
        return 1
    if any(keyword in text for keyword in ("缺席", "停赛", "受伤", "单独训练", "待确认", "高温", "紧张")):
        return -1
    return 0


def infer_event_strength(text: str) -> float:
    if any(keyword in text for keyword in ("停赛", "缺席", "受伤")):
        return 0.055
    if any(keyword in text for keyword in ("主力", "核心", "连续两天")):
        return 0.035
    if any(keyword in text for keyword in ("高温", "天气", "恢复")):
        return 0.02
    return 0.015


PUBLIC_PROXY_CATEGORY_STRENGTH = {
    "suspension": 0.07,
    "injury": 0.062,
    "player_status": 0.064,
    "availability": 0.048,
    "lineup": 0.045,
    "xg_proxy": 0.052,
    "market_proxy": 0.028,
    "weather": 0.028,
    "training": 0.026,
    "general": 0.015,
}


def clamp_public_signal(value: float, lower: float = 0.005, upper: float = 0.095) -> float:
    return max(lower, min(upper, value))


def public_proxy_event_strength(item: RawNewsItem, text: str) -> float:
    if item.category is None and item.confidence is None and not item.players:
        return infer_event_strength(text)

    base = PUBLIC_PROXY_CATEGORY_STRENGTH.get(str(item.category or "general"), infer_event_strength(text))
    confidence = item.confidence if isinstance(item.confidence, (int, float)) else 0.55
    confidence = max(0.0, min(1.0, float(confidence)))
    confidence_multiplier = 0.75 + confidence * 0.45
    player_bonus = min(len(item.players or []) * 0.008, 0.024)
    return round(clamp_public_signal(base * confidence_multiplier + player_bonus), 4)


def action_for_news_item(item: RawNewsItem, source: NewsSource) -> str:
    if item.status in {"unverified", "rumor"} or source.source_level == "D":
        return "ignore"
    if source.source_level == "C" and item.status in {"confirmed", "multi_source"}:
        return "apply"
    if source.source_level == "C":
        return "watch"
    return "apply"


def events_from_raw_news(items: list[RawNewsItem], news_sources: dict[str, NewsSource]) -> list[TeamEvent]:
    events: list[TeamEvent] = []
    cross_verified_ids: set[str] = set()
    grouped_items: dict[tuple[str | None, str, int], set[str]] = {}
    item_signatures: dict[str, tuple[str | None, str, int]] = {}
    for item in items:
        source = news_sources[item.source]
        if item.status != "single_source" or source.source_level != "C":
            continue
        text = f"{item.title} {item.summary}"
        signature = (
            item.team,
            item.factor or infer_event_factor(text),
            item.direction if item.direction is not None else infer_event_direction(text),
        )
        item_signatures[item.id] = signature
        grouped_items.setdefault(signature, set()).add(item.source)
    for item in items:
        signature = item_signatures.get(item.id)
        if signature is not None and len(grouped_items[signature]) >= 2:
            cross_verified_ids.add(item.id)

    for item in items:
        source = news_sources[item.source]
        text = f"{item.title} {item.summary}"
        status = "multi_source" if item.id in cross_verified_ids else item.status
        action = action_for_news_item(
            RawNewsItem(
                id=item.id,
                title=item.title,
                summary=item.summary,
                source=item.source,
                team=item.team,
                status=status,
                published_at=item.published_at,
                url=item.url,
            ),
            source,
        )
        events.append(
            TeamEvent(
                title=item.title,
                detail=item.summary,
                team=item.team,
                source_level=source.source_level,
                factor=item.factor or infer_event_factor(text),
                direction=item.direction if item.direction is not None else infer_event_direction(text),
                strength=public_proxy_event_strength(item, text),
                time=item.published_at,
                source=source.name,
                url=item.url,
                status=status,
                action=action,
                id=item.id,
            )
        )
    return events


def load_third_place_combinations() -> dict[str, dict[str, str]]:
    data = read_json_file("third-place-combinations.json")
    combinations = data["combinations"]
    if len(combinations) != 495:
        raise ValueError("小组第三组合表必须包含 495 种组合")
    return combinations


def load_current_match() -> tuple[str, str]:
    row = read_json_file("current-match.json")
    return row["home"], row["away"]


def load_tournament_provenance(teams_path: Path | None = None) -> dict[str, object]:
    provenance_path = (teams_path.parent if teams_path is not None else DATA_DIR) / TOURNAMENT_PROVENANCE_FILE
    if not provenance_path.exists():
        return {"source": "local-json"}
    return json.loads(provenance_path.read_text(encoding="utf-8"))


def load_runtime_dataset(
    raw_news_path: Path | None = None,
    fixtures_path: Path | None = None,
    teams_path: Path | None = None,
) -> RuntimeDataset:
    team_profiles = load_team_profiles(teams_path)
    fixtures = load_fixtures(team_profiles, fixtures_path)
    source_weights = load_source_weights()
    news_sources = load_news_sources(source_weights)
    drop_incompatible_team_events = teams_path is not None
    raw_news_items = load_raw_news_items(
        team_profiles,
        news_sources,
        raw_news_path,
        drop_unknown_teams=drop_incompatible_team_events,
    )
    manual_events = load_events(team_profiles, drop_unknown_teams=drop_incompatible_team_events)
    events = manual_events + events_from_raw_news(raw_news_items, news_sources)
    third_place_combinations = load_third_place_combinations()
    current_match = load_current_match()
    tournament_provenance = load_tournament_provenance(teams_path)
    dataset_meta = {
        "source": tournament_provenance.get("source", "local-json"),
        "tournamentSource": tournament_provenance,
        "teamCount": len(team_profiles),
        "groupCount": len(WORLD_CUP_GROUPS),
        "fixtureCount": len(fixtures),
        "eventCount": len(events),
        "manualEventCount": len(manual_events),
        "rawNewsCount": len(raw_news_items),
        "newsSourceCount": len(news_sources),
        "placeholderSlots": len([team for team in team_profiles.values() if team.key.startswith("slot-")]),
    }
    return RuntimeDataset(
        team_profiles=team_profiles,
        fixtures=fixtures,
        source_weights=source_weights,
        news_sources=news_sources,
        raw_news_items=raw_news_items,
        manual_events=manual_events,
        events=events,
        third_place_combinations=third_place_combinations,
        current_match=current_match,
        dataset_meta=dataset_meta,
    )


def apply_runtime_dataset(dataset: RuntimeDataset) -> RuntimeDataset:
    global TEAM_PROFILES, FIXTURES, SOURCE_WEIGHTS, NEWS_SOURCES, RAW_NEWS_ITEMS
    global MANUAL_EVENTS, EVENTS, THIRD_PLACE_COMBINATIONS, CURRENT_MATCH, DATASET_META
    TEAM_PROFILES = dataset.team_profiles
    FIXTURES = dataset.fixtures
    SOURCE_WEIGHTS = dataset.source_weights
    NEWS_SOURCES = dataset.news_sources
    RAW_NEWS_ITEMS = dataset.raw_news_items
    MANUAL_EVENTS = dataset.manual_events
    EVENTS = dataset.events
    THIRD_PLACE_COMBINATIONS = dataset.third_place_combinations
    CURRENT_MATCH = dataset.current_match
    DATASET_META = dataset.dataset_meta
    return dataset


def reload_runtime_data(
    raw_news_path: Path | None = None,
    fixtures_path: Path | None = None,
    teams_path: Path | None = None,
) -> RuntimeDataset:
    return apply_runtime_dataset(load_runtime_dataset(raw_news_path, fixtures_path, teams_path))


apply_runtime_dataset(load_runtime_dataset())
