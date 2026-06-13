from __future__ import annotations

from bisect import bisect_left
from collections import defaultdict
from dataclasses import replace
from datetime import datetime, timezone
from math import exp, factorial
from random import Random
from pathlib import Path
from typing import Literal

from . import data as data_state
from .data import (
    CURRENT_MATCH,
    DATASET_META,
    EVENTS,
    FIXTURES,
    SOURCE_WEIGHTS,
    TEAM_PROFILES,
    THIRD_PLACE_COMBINATIONS,
    Fixture,
    TeamProfile,
)

Outcome = Literal["home", "draw", "away"]

SIMULATION_COUNT = 8_000
MAX_GOALS = 7
EVENT_FACTORS = ("attack", "defense", "goalkeeper", "path", "squad")
LIVE_REMAINING_GOAL_RATE = 0.45

# NOTE: 固定路径来自 FIFA World Cup 26 Regulations Article 12.6-12.11 和 Annexe C。
ROUND_OF_32_MATCHES = (
    (73, ("runnerUp", "A"), ("runnerUp", "B")),
    (74, ("winner", "E"), ("third", "ABCDF")),
    (75, ("winner", "F"), ("runnerUp", "C")),
    (76, ("winner", "C"), ("runnerUp", "F")),
    (77, ("winner", "I"), ("third", "CDFGH")),
    (78, ("runnerUp", "E"), ("runnerUp", "I")),
    (79, ("winner", "A"), ("third", "CEFHI")),
    (80, ("winner", "L"), ("third", "EHIJK")),
    (81, ("winner", "D"), ("third", "BEFIJ")),
    (82, ("winner", "G"), ("third", "AEHIJ")),
    (83, ("runnerUp", "K"), ("runnerUp", "L")),
    (84, ("winner", "H"), ("runnerUp", "J")),
    (85, ("winner", "B"), ("third", "EFGIJ")),
    (86, ("winner", "J"), ("runnerUp", "H")),
    (87, ("winner", "K"), ("third", "DEIJL")),
    (88, ("runnerUp", "D"), ("runnerUp", "G")),
)
ROUND_OF_16_MATCHES = (
    (89, 74, 77),
    (90, 73, 75),
    (91, 76, 78),
    (92, 79, 80),
    (93, 83, 84),
    (94, 81, 82),
    (95, 86, 88),
    (96, 85, 87),
)
QUARTERFINAL_MATCHES = ((97, 89, 90), (98, 93, 94), (99, 91, 92), (100, 95, 96))
SEMIFINAL_MATCHES = ((101, 97, 98), (102, 99, 100))
THIRD_PLACE_WINNER_MATCHES = {"A": 79, "B": 85, "D": 81, "E": 74, "G": 82, "I": 77, "K": 87, "L": 80}


def reload_model_data(raw_news_path: Path | None = None, fixtures_path: Path | None = None):
    dataset = data_state.reload_runtime_data(raw_news_path, fixtures_path)
    global CURRENT_MATCH, DATASET_META, EVENTS, FIXTURES, SOURCE_WEIGHTS, TEAM_PROFILES, THIRD_PLACE_COMBINATIONS
    CURRENT_MATCH = dataset.current_match
    DATASET_META = dataset.dataset_meta
    EVENTS = dataset.events
    FIXTURES = dataset.fixtures
    SOURCE_WEIGHTS = dataset.source_weights
    TEAM_PROFILES = dataset.team_profiles
    THIRD_PLACE_COMBINATIONS = dataset.third_place_combinations
    return dataset


def event_factor_impacts() -> dict[str, dict[str, float]]:
    impacts = {team_key: {factor: 0.0 for factor in EVENT_FACTORS} for team_key in TEAM_PROFILES}
    for event in EVENTS:
        weight = SOURCE_WEIGHTS[event.source_level]
        if not event_enters_model(event) or event.factor not in EVENT_FACTORS:
            continue
        impacts[event.team][event.factor] += round(event.direction * event.strength * weight * 100, 2)
    return impacts


def profile_to_plates(profile: TeamProfile) -> dict[str, int]:
    return {
        "strength": round((profile.elo - 1000) / 10),
        "form": round((profile.attack + profile.defense) / 2),
        "path": profile.path,
        "squad": profile.squad,
        "margin": round((profile.goalkeeper + profile.defense) / 2),
    }


def apply_event_adjustments() -> dict[str, TeamProfile]:
    adjusted = dict(TEAM_PROFILES)
    impacts = event_factor_impacts()
    for team_key, factor_impacts in impacts.items():
        team = adjusted[team_key]
        attack_delta = int(round(factor_impacts["attack"]))
        defense_delta = int(round(factor_impacts["defense"]))
        goalkeeper_delta = int(round(factor_impacts["goalkeeper"]))
        path_delta = int(round(factor_impacts["path"]))
        squad_delta = int(round(factor_impacts["squad"]))
        adjusted[team_key] = replace(
            team,
            attack=max(50, min(99, team.attack + attack_delta)),
            defense=max(50, min(99, team.defense + defense_delta)),
            goalkeeper=max(50, min(99, team.goalkeeper + goalkeeper_delta)),
            path=max(50, min(99, team.path + path_delta)),
            squad=max(50, min(99, team.squad + squad_delta)),
        )
    return adjusted


def poisson_probability(lam: float, goals: int) -> float:
    return (lam**goals * exp(-lam)) / factorial(goals)


def expected_goals(home: TeamProfile, away: TeamProfile) -> tuple[float, float]:
    elo_gap = home.elo - away.elo
    home_attack = home.attack / 86
    away_attack = away.attack / 86
    home_against = 2.08 - away.defense / 86
    away_against = 2.08 - home.defense / 86
    home_squad = home.squad / 85
    away_squad = away.squad / 85
    home_goalkeeper_drag = 2.02 - away.goalkeeper / 86
    away_goalkeeper_drag = 2.02 - home.goalkeeper / 86

    home_lambda = 1.35 * exp(elo_gap / 760) * home_attack * home_against * home_squad * home_goalkeeper_drag
    away_lambda = 1.22 * exp(-elo_gap / 760) * away_attack * away_against * away_squad * away_goalkeeper_drag
    return max(0.35, min(3.25, home_lambda)), max(0.35, min(3.25, away_lambda))


def score_distribution(home_key: str, away_key: str, teams: dict[str, TeamProfile]) -> list[dict[str, float | str]]:
    home_lambda, away_lambda = expected_goals(teams[home_key], teams[away_key])
    return score_distribution_from_lambdas(home_lambda, away_lambda)


def score_distribution_from_lambdas(home_lambda: float, away_lambda: float) -> list[dict[str, float | str]]:
    distribution = []
    for home_goals in range(MAX_GOALS + 1):
        for away_goals in range(MAX_GOALS + 1):
            probability = poisson_probability(home_lambda, home_goals) * poisson_probability(away_lambda, away_goals)
            distribution.append(
                {
                    "score": f"{home_goals}-{away_goals}",
                    "homeGoals": home_goals,
                    "awayGoals": away_goals,
                    "probability": probability,
                }
            )
    return sorted(distribution, key=lambda item: float(item["probability"]), reverse=True)


def win_draw_loss(home_key: str, away_key: str, teams: dict[str, TeamProfile]) -> dict[str, float]:
    distribution = score_distribution(home_key, away_key, teams)
    home = sum(float(item["probability"]) for item in distribution if int(item["homeGoals"]) > int(item["awayGoals"]))
    draw = sum(float(item["probability"]) for item in distribution if int(item["homeGoals"]) == int(item["awayGoals"]))
    away = sum(float(item["probability"]) for item in distribution if int(item["homeGoals"]) < int(item["awayGoals"]))
    total = home + draw + away
    return {
        "home": home / total,
        "draw": draw / total,
        "away": away / total,
    }


def build_score_sampler(home_key: str, away_key: str, teams: dict[str, TeamProfile]) -> list[tuple[float, int, int]]:
    home_lambda, away_lambda = expected_goals(teams[home_key], teams[away_key])
    return build_score_sampler_from_lambdas(home_lambda, away_lambda)


def build_score_sampler_from_lambdas(home_lambda: float, away_lambda: float) -> list[tuple[float, int, int]]:
    distribution = score_distribution_from_lambdas(home_lambda, away_lambda)
    total = sum(float(item["probability"]) for item in distribution)
    cumulative = 0.0
    sampler = []
    for item in distribution:
        cumulative += float(item["probability"]) / total
        sampler.append((cumulative, int(item["homeGoals"]), int(item["awayGoals"])))
    final_cumulative, final_home, final_away = sampler[-1]
    sampler[-1] = (1.0, final_home, final_away)
    return sampler


def sample_score_from_distribution(distribution: list[dict[str, float | str]], rng: Random) -> tuple[int, int]:
    target = rng.random()
    cumulative = 0.0
    for item in distribution:
        cumulative += float(item["probability"])
        if cumulative >= target:
            return int(item["homeGoals"]), int(item["awayGoals"])
    fallback = distribution[0]
    return int(fallback["homeGoals"]), int(fallback["awayGoals"])


def sample_score_from_sampler(sampler: list[tuple[float, int, int]], rng: Random) -> tuple[int, int]:
    index = bisect_left(sampler, (rng.random(), -1, -1))
    if index >= len(sampler):
        index = len(sampler) - 1
    _, home_goals, away_goals = sampler[index]
    return home_goals, away_goals


def build_fixture_score_sampler(fixture: Fixture, teams: dict[str, TeamProfile]) -> list[tuple[float, int, int]]:
    home_lambda, away_lambda = expected_goals(teams[fixture.home], teams[fixture.away])
    if fixture.status == "live" and fixture.home_score is not None and fixture.away_score is not None:
        return build_score_sampler_from_lambdas(
            max(0.1, home_lambda * LIVE_REMAINING_GOAL_RATE),
            max(0.1, away_lambda * LIVE_REMAINING_GOAL_RATE),
        )
    return build_score_sampler_from_lambdas(home_lambda, away_lambda)


def sample_fixture_score(
    fixture: Fixture,
    teams: dict[str, TeamProfile],
    rng: Random,
    sampler: list[tuple[float, int, int]] | None = None,
) -> tuple[int, int]:
    sampler = sampler or build_fixture_score_sampler(fixture, teams)
    home_goals, away_goals = sample_score_from_sampler(sampler, rng)
    if fixture.status == "live" and fixture.home_score is not None and fixture.away_score is not None:
        return fixture.home_score + home_goals, fixture.away_score + away_goals
    return home_goals, away_goals


def forced_outcome_score(fixture: Fixture, outcome: Outcome) -> tuple[int, int]:
    base_home = fixture.home_score if fixture.status == "live" and fixture.home_score is not None else 0
    base_away = fixture.away_score if fixture.status == "live" and fixture.away_score is not None else 0
    if outcome == "home":
        return max(base_home, base_away + 1), base_away
    if outcome == "draw":
        target = max(base_home, base_away)
        return target, target
    return base_home, max(base_away, base_home + 1)


def build_standings(fixtures: list[Fixture]) -> dict[str, dict[str, int]]:
    standings = {
        key: {"points": 0, "gf": 0, "ga": 0, "gd": 0, "wins": 0}
        for key in TEAM_PROFILES
    }
    for fixture in fixtures:
        if fixture.home_score is None or fixture.away_score is None:
            continue
        home = standings[fixture.home]
        away = standings[fixture.away]
        home["gf"] += fixture.home_score
        home["ga"] += fixture.away_score
        away["gf"] += fixture.away_score
        away["ga"] += fixture.home_score
        home["gd"] = home["gf"] - home["ga"]
        away["gd"] = away["gf"] - away["ga"]
        if fixture.home_score > fixture.away_score:
            home["points"] += 3
            home["wins"] += 1
        elif fixture.home_score < fixture.away_score:
            away["points"] += 3
            away["wins"] += 1
        else:
            home["points"] += 1
            away["points"] += 1
    return standings


def group_names(teams: dict[str, TeamProfile]) -> list[str]:
    return sorted({team.group for team in teams.values()})


def rank_group(
    standings: dict[str, dict[str, int]],
    group: str,
    rng: Random | None = None,
    teams: dict[str, TeamProfile] | None = None,
) -> list[str]:
    rng = rng or Random(0)
    teams = teams or TEAM_PROFILES
    group_teams = [team_key for team_key, team in teams.items() if team.group == group]
    return sorted(
        group_teams,
        key=lambda key: (
            standings[key]["points"],
            standings[key]["gd"],
            standings[key]["gf"],
            standings[key]["wins"],
            rng.random(),
        ),
        reverse=True,
    )


def best_third_place_teams(
    standings: dict[str, dict[str, int]],
    teams: dict[str, TeamProfile],
    rng: Random | None = None,
    rankings: dict[str, list[str]] | None = None,
) -> list[str]:
    rng = rng or Random(0)
    rankings = rankings or {group: rank_group(standings, group, rng, teams) for group in group_names(teams)}
    third_place = [rankings[group][2] for group in group_names(teams)]
    return sorted(
        third_place,
        key=lambda key: (
            standings[key]["points"],
            standings[key]["gd"],
            standings[key]["gf"],
            standings[key]["wins"],
            rng.random(),
        ),
        reverse=True,
    )[:8]


def match_win_probability(team_key: str, virtual_rating: int, teams: dict[str, TeamProfile], rng: Random) -> bool:
    team = teams[team_key]
    rating_gap = team.elo + (team.attack - 86) * 6 + (team.defense - 84) * 4 + (team.squad - 84) * 4 - virtual_rating
    probability = 1 / (1 + exp(-rating_gap / 210))
    return rng.random() < probability


def team_knockout_rating(team_key: str, teams: dict[str, TeamProfile]) -> int:
    team = teams[team_key]
    return team.elo + (team.attack - 86) * 6 + (team.defense - 84) * 4 + (team.squad - 84) * 4


def head_to_head_winner(team_a: str, team_b: str, teams: dict[str, TeamProfile], rng: Random) -> str:
    rating_gap = team_knockout_rating(team_a, teams) - team_knockout_rating(team_b, teams)
    probability = 1 / (1 + exp(-rating_gap / 210))
    return team_a if rng.random() < probability else team_b


def assign_third_place_slots(
    third_place: list[str],
    teams: dict[str, TeamProfile],
) -> dict[int, str]:
    third_by_group = {teams[team_key].group: team_key for team_key in third_place}
    combination_key = "".join(sorted(third_by_group))
    annex_assignment = THIRD_PLACE_COMBINATIONS.get(combination_key)
    if annex_assignment is not None:
        return {
            THIRD_PLACE_WINNER_MATCHES[winner_group]: third_by_group[third_group]
            for winner_group, third_group in annex_assignment.items()
        }

    slots = [
        (match_no, seed[1])
        for match_no, _, seed in ROUND_OF_32_MATCHES
        if seed[0] == "third"
    ]
    ranked_groups = tuple(teams[team_key].group for team_key in third_place)
    rank_index = {group: index for index, group in enumerate(ranked_groups)}

    def search(index: int, remaining_groups: tuple[str, ...]) -> dict[int, str] | None:
        if index == len(slots):
            return {}
        match_no, allowed_groups = slots[index]
        candidates = sorted(
            [group for group in remaining_groups if group in allowed_groups],
            key=lambda group: rank_index[group],
        )
        for group in candidates:
            next_remaining = tuple(item for item in remaining_groups if item != group)
            result = search(index + 1, next_remaining)
            if result is not None:
                return {match_no: third_by_group[group], **result}
        return None

    assigned = search(0, ranked_groups)
    if assigned is None:
        return {match_no: third_place[index] for index, (match_no, _) in enumerate(slots)}
    return assigned


def resolve_round_seed(
    seed: tuple[str, str],
    match_no: int,
    rankings: dict[str, list[str]],
    third_assignments: dict[int, str],
) -> str:
    seed_type, value = seed
    if seed_type == "winner":
        return rankings[value][0]
    if seed_type == "runnerUp":
        return rankings[value][1]
    return third_assignments[match_no]


def build_round_of_32_matches(
    rankings: dict[str, list[str]],
    third_place: list[str],
    teams: dict[str, TeamProfile],
) -> dict[int, tuple[str, str]]:
    third_assignments = assign_third_place_slots(third_place, teams)
    return {
        match_no: (
            resolve_round_seed(left_seed, match_no, rankings, third_assignments),
            resolve_round_seed(right_seed, match_no, rankings, third_assignments),
        )
        for match_no, left_seed, right_seed in ROUND_OF_32_MATCHES
    }


def play_bracket_matches(
    matchups: dict[int, tuple[str, str]],
    teams: dict[str, TeamProfile],
    rng: Random,
    counts,
    stage: str,
) -> dict[int, str]:
    winners = {}
    for match_no, (team_a, team_b) in matchups.items():
        winner = head_to_head_winner(team_a, team_b, teams, rng)
        winners[match_no] = winner
        counts[winner][stage] += 1
    return winners


def build_next_round_matchups(
    bracket: tuple[tuple[int, int, int], ...],
    previous_winners: dict[int, str],
) -> dict[int, tuple[str, str]]:
    return {
        match_no: (previous_winners[left_match], previous_winners[right_match])
        for match_no, left_match, right_match in bracket
    }


def simulate_tournament(
    teams: dict[str, TeamProfile],
    forced_current: Outcome | None = None,
    simulation_count: int = SIMULATION_COUNT,
    forced_match: tuple[str, str] | None = None,
) -> dict[str, dict[str, float]]:
    stages = ("roundOf32", "roundOf16", "quarterfinal", "semifinal", "final", "champion")
    counts = defaultdict(lambda: {stage: 0 for stage in stages})
    rng = Random(20260614 + (0 if forced_current is None else {"home": 11, "draw": 22, "away": 33}[forced_current]))
    forced_match = forced_match or CURRENT_MATCH
    distribution_cache = {
        (fixture.home, fixture.away, fixture.status, fixture.home_score, fixture.away_score): build_fixture_score_sampler(fixture, teams)
        for fixture in FIXTURES
        if fixture.status != "finished"
    }

    for _ in range(simulation_count):
        simulated_fixtures: list[Fixture] = []
        for fixture in FIXTURES:
            if fixture.status == "finished":
                simulated_fixtures.append(fixture)
                continue
            if (fixture.home, fixture.away) == forced_match and forced_current is not None:
                score = forced_outcome_score(fixture, forced_current)
            else:
                cache_key = (fixture.home, fixture.away, fixture.status, fixture.home_score, fixture.away_score)
                score = sample_fixture_score(fixture, teams, rng, distribution_cache[cache_key])
            simulated_fixtures.append(
                Fixture(fixture.home, fixture.away, fixture.stage, fixture.kickoff, fixture.status, score[0], score[1])
            )

        standings = build_standings(simulated_fixtures)
        groups = group_names(teams)
        rankings = {group: rank_group(standings, group, rng, teams) for group in groups}
        top_two = [team_key for group in groups for team_key in rankings[group][:2]]
        third_place = best_third_place_teams(standings, teams, rng, rankings)
        round_teams = top_two + third_place
        for team_key in round_teams:
            counts[team_key]["roundOf32"] += 1
        round_of_32 = build_round_of_32_matches(rankings, third_place, teams)
        round_of_32_winners = play_bracket_matches(round_of_32, teams, rng, counts, "roundOf16")
        round_of_16 = build_next_round_matchups(ROUND_OF_16_MATCHES, round_of_32_winners)
        round_of_16_winners = play_bracket_matches(round_of_16, teams, rng, counts, "quarterfinal")
        quarterfinals = build_next_round_matchups(QUARTERFINAL_MATCHES, round_of_16_winners)
        quarterfinal_winners = play_bracket_matches(quarterfinals, teams, rng, counts, "semifinal")
        semifinals = build_next_round_matchups(SEMIFINAL_MATCHES, quarterfinal_winners)
        semifinal_winners = play_bracket_matches(semifinals, teams, rng, counts, "final")
        champion = head_to_head_winner(semifinal_winners[101], semifinal_winners[102], teams, rng)
        counts[champion]["champion"] += 1

    return {
        team_key: {
            stage: round(counts[team_key][stage] / simulation_count * 100, 1)
            for stage in stages
        }
        for team_key in teams
    }


def tone_for_probability(index: int) -> str:
    return ["gold", "green", "blue"][index] if index < 3 else "muted"


def signed_percent(value: float) -> str:
    if abs(value) < 0.05:
        return "±0.0%"
    return f"{value:+.1f}%"


def event_to_news_item(event) -> dict[str, str]:
    weight = SOURCE_WEIGHTS[event.source_level]
    if event.action == "ignore" or weight == 0:
        impact = "不入模型"
        tone = "muted"
    elif event.action == "watch":
        impact = "待审核"
        tone = "gold"
    elif event.team is None:
        impact = "全局备注"
        tone = "green"
    elif weight < 0.5:
        impact = "轻微修正"
        tone = "gold"
    else:
        impact = "可入模型"
        tone = "green" if event.direction >= 0 else "orange"
    return {
        "title": event.title,
        "detail": event.detail,
        "impact": impact,
        "tone": tone,
        "time": event.time,
    }


def event_summary() -> dict[str, int]:
    return {
        "watched": len(EVENTS),
        "applied": len([event for event in EVENTS if event_enters_model(event)]),
        "ignored": len([event for event in EVENTS if event.action == "ignore" or SOURCE_WEIGHTS[event.source_level] == 0]),
        "reviewRequired": len([event for event in EVENTS if event.action == "watch"]),
    }


def event_enters_model(event) -> bool:
    return event.action == "apply" and SOURCE_WEIGHTS[event.source_level] > 0 and event.team is not None


def build_scenario_impacts(
    base: dict[str, dict[str, float]],
    home_key: str,
    away_key: str,
    probabilities: dict[str, float],
    teams: dict[str, TeamProfile],
    simulation_count: int,
) -> list[dict[str, object]]:
    scenarios: list[tuple[Outcome, str, str]] = [
        ("home", f"{teams[home_key].name}胜", f"{teams[home_key].name}小组第一概率上升"),
        ("draw", "打平", "两队路径保持胶着"),
        ("away", f"{teams[away_key].name}胜", f"{teams[away_key].name}半区压力下降"),
    ]
    items = []
    for outcome, label, title in scenarios:
        scenario = simulate_tournament(teams, outcome, simulation_count, (home_key, away_key))
        home_shift = scenario[home_key]["champion"] - base[home_key]["champion"]
        away_shift = scenario[away_key]["champion"] - base[away_key]["champion"]
        if outcome == "draw":
            details = [
                f"{teams[home_key].name}夺冠概率 {signed_percent(home_shift)}",
                f"{teams[away_key].name}夺冠概率 {signed_percent(away_shift)}",
                "小组第一仍取决于末轮和净胜球",
            ]
            champion_shift = f"{signed_percent(home_shift)} / {signed_percent(away_shift)}"
            tone = "gold"
        elif outcome == "home":
            details = [
                f"{teams[home_key].name}夺冠概率 {signed_percent(home_shift)}",
                f"{teams[away_key].name}路径盘下调 {signed_percent(away_shift)}",
                "同组竞争队出线门槛抬高",
            ]
            champion_shift = signed_percent(home_shift)
            tone = "green"
        else:
            details = [
                f"{teams[away_key].name}夺冠概率 {signed_percent(away_shift)}",
                f"{teams[home_key].name}潜在淘汰赛路径变难 {signed_percent(home_shift)}",
                "小组第二路径风险上升",
            ]
            champion_shift = signed_percent(away_shift)
            tone = "blue"
        items.append(
            {
                "label": label,
                "probability": round(probabilities[outcome] * 100),
                "title": title,
                "details": details,
                "championShift": champion_shift,
                "tone": tone,
            }
        )
    return items


def score_outcomes_for_match(home_key: str, away_key: str, teams: dict[str, TeamProfile]) -> list[dict[str, object]]:
    distribution = score_distribution(home_key, away_key, teams)
    return [
        {
            "score": item["score"],
            "probability": round(float(item["probability"]) * 100, 1),
            "note": ["双方基础强度接近", "边路优势可能放大", "低比分胜局仍有空间"][index],
            "tone": tone_for_probability(index),
        }
        for index, item in enumerate(distribution[:3])
    ]


def build_match_detail(home_key: str, away_key: str, simulation_count: int = 1200) -> dict[str, object]:
    teams = apply_event_adjustments()
    current_fixture = next((fixture for fixture in FIXTURES if (fixture.home, fixture.away) == (home_key, away_key)), None)
    if current_fixture is None:
        raise ValueError(f"找不到比赛: {home_key} vs {away_key}")

    probabilities = win_draw_loss(home_key, away_key, teams)
    home_win = round(probabilities["home"] * 100)
    draw = round(probabilities["draw"] * 100)
    away_win = 100 - home_win - draw
    base_tournament = simulate_tournament(teams, simulation_count=simulation_count)

    return {
        "stage": current_fixture.stage,
        "kickoff": current_fixture.kickoff,
        "status": "未开赛" if current_fixture.status == "scheduled" else current_fixture.status,
        "homeTeam": home_key,
        "awayTeam": away_key,
        "homeWin": home_win,
        "draw": draw,
        "awayWin": away_win,
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "scoreOutcomes": score_outcomes_for_match(home_key, away_key, teams),
        "scenarioImpacts": build_scenario_impacts(base_tournament, home_key, away_key, probabilities, teams, simulation_count),
        "analysis": [
            f"{teams[home_key].name}单场胜率 {home_win}%，当前差距主要来自基础实力和攻防盘。",
            f"平局概率 {draw}%，会继续放大小组排名和净胜球权重。",
            "该场结果会被传导进小组排名、淘汰赛路径和冠军概率。",
        ],
    }


def build_upcoming_match_predictions(limit: int = 12) -> dict[str, object]:
    teams = apply_event_adjustments()
    items = []
    for fixture in FIXTURES:
        if fixture.status != "scheduled":
            continue
        probabilities = win_draw_loss(fixture.home, fixture.away, teams)
        home_win = round(probabilities["home"] * 100)
        draw = round(probabilities["draw"] * 100)
        away_win = 100 - home_win - draw
        top_score = score_distribution(fixture.home, fixture.away, teams)[0]
        items.append(
            {
                "stage": fixture.stage,
                "kickoff": fixture.kickoff,
                "status": fixture.status,
                "homeTeam": fixture.home,
                "awayTeam": fixture.away,
                "homeName": teams[fixture.home].name,
                "awayName": teams[fixture.away].name,
                "homeCode": teams[fixture.home].code,
                "awayCode": teams[fixture.away].code,
                "homeWin": home_win,
                "draw": draw,
                "awayWin": away_win,
                "topScore": {
                    "score": top_score["score"],
                    "probability": round(float(top_score["probability"]) * 100, 1),
                },
            }
        )
        if len(items) >= limit:
            break
    return {
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "count": len(items),
        "items": items,
    }


def build_match_prediction(simulation_count: int = SIMULATION_COUNT) -> dict[str, object]:
    teams = apply_event_adjustments()
    home_key, away_key = CURRENT_MATCH
    current_fixture = next(fixture for fixture in FIXTURES if (fixture.home, fixture.away) == CURRENT_MATCH)
    probabilities = win_draw_loss(home_key, away_key, teams)
    base_tournament = simulate_tournament(teams, simulation_count=simulation_count)

    response_teams = []
    for team_key, profile in teams.items():
        tournament = base_tournament[team_key]
        response_teams.append(
            {
                "key": profile.key,
                "name": profile.name,
                "code": profile.code,
                "factors": profile_to_plates(profile),
                "tournament": {
                    "champion": tournament["champion"],
                    "final": tournament["final"],
                    "semifinal": tournament["semifinal"],
                    "quarterfinal": tournament["quarterfinal"],
                    "change": round(tournament["champion"] - TEAM_PROFILES[team_key].path / 8, 1),
                },
            }
        )

    analysis = [
        f"{teams[home_key].name}单场胜率 {round(probabilities['home'] * 100)}%，优势来自基础实力和进攻盘。",
        f"平局概率 {round(probabilities['draw'] * 100)}%，会让小组第一继续依赖末轮赛果。",
        "已结束比赛已经锁定进积分表，伤病和停赛只按来源权重小幅修正。",
    ]

    return {
        "stage": current_fixture.stage,
        "kickoff": current_fixture.kickoff,
        "status": "未开赛",
        "homeTeam": home_key,
        "awayTeam": away_key,
        "homeWin": round(probabilities["home"] * 100),
        "draw": round(probabilities["draw"] * 100),
        "awayWin": round(probabilities["away"] * 100),
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "scoreOutcomes": score_outcomes_for_match(home_key, away_key, teams),
        "scenarioImpacts": build_scenario_impacts(base_tournament, home_key, away_key, probabilities, teams, simulation_count),
        "analysis": analysis,
        "newsItems": [event_to_news_item(event) for event in EVENTS],
        "teams": response_teams,
        "modelMeta": {
            "engine": "Poisson + Monte Carlo",
            "simulationCount": simulation_count,
            "lockedResults": len([fixture for fixture in FIXTURES if fixture.status == "finished"]),
            "dataset": DATASET_META,
            "events": event_summary(),
            "factorImpacts": event_factor_impacts(),
        },
    }
