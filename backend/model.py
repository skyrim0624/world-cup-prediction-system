from __future__ import annotations

from bisect import bisect_left
from collections import defaultdict
from dataclasses import replace
from datetime import datetime, timezone
from math import exp, factorial
from random import Random
from typing import Literal

from .data import CURRENT_MATCH, DATASET_META, EVENTS, FIXTURES, SOURCE_WEIGHTS, TEAM_PROFILES, Fixture, TeamProfile

Outcome = Literal["home", "draw", "away"]

SIMULATION_COUNT = 8_000
MAX_GOALS = 7
EVENT_FACTORS = ("attack", "defense", "goalkeeper", "path", "squad")


def event_factor_impacts() -> dict[str, dict[str, float]]:
    impacts = {team_key: {factor: 0.0 for factor in EVENT_FACTORS} for team_key in TEAM_PROFILES}
    for event in EVENTS:
        weight = SOURCE_WEIGHTS[event.source_level]
        if weight <= 0 or event.team is None or event.factor not in EVENT_FACTORS:
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
    distribution = score_distribution(home_key, away_key, teams)
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
) -> list[str]:
    rng = rng or Random(0)
    third_place = [rank_group(standings, group, rng, teams)[2] for group in group_names(teams)]
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


def simulate_tournament(
    teams: dict[str, TeamProfile],
    forced_current: Outcome | None = None,
    simulation_count: int = SIMULATION_COUNT,
) -> dict[str, dict[str, float]]:
    stages = ("roundOf32", "roundOf16", "quarterfinal", "semifinal", "final", "champion")
    counts = defaultdict(lambda: {stage: 0 for stage in stages})
    rng = Random(20260614 + (0 if forced_current is None else {"home": 11, "draw": 22, "away": 33}[forced_current]))
    distribution_cache = {
        (fixture.home, fixture.away): build_score_sampler(fixture.home, fixture.away, teams)
        for fixture in FIXTURES
        if fixture.status != "finished"
    }

    for _ in range(simulation_count):
        simulated_fixtures: list[Fixture] = []
        for fixture in FIXTURES:
            if fixture.status == "finished":
                simulated_fixtures.append(fixture)
                continue
            if (fixture.home, fixture.away) == CURRENT_MATCH and forced_current is not None:
                score = {"home": (1, 0), "draw": (1, 1), "away": (0, 1)}[forced_current]
            else:
                score = sample_score_from_sampler(distribution_cache[(fixture.home, fixture.away)], rng)
            simulated_fixtures.append(
                Fixture(fixture.home, fixture.away, fixture.stage, fixture.kickoff, fixture.status, score[0], score[1])
            )

        standings = build_standings(simulated_fixtures)
        groups = group_names(teams)
        group_qualifiers = {group: rank_group(standings, group, rng, teams)[:2] for group in groups}
        top_two = [team_key for group in groups for team_key in group_qualifiers[group]]
        third_place = best_third_place_teams(standings, teams, rng)
        round_teams = top_two + third_place
        round_teams = sorted(
            round_teams,
            key=lambda key: (
                standings[key]["points"],
                standings[key]["gd"],
                teams[key].elo,
                rng.random(),
            ),
            reverse=True,
        )
        for team_key in round_teams:
            counts[team_key]["roundOf32"] += 1

        for next_stage in ("roundOf16", "quarterfinal", "semifinal", "final", "champion"):
            winners = []
            bracket = list(round_teams)
            for index in range(0, len(bracket), 2):
                if index + 1 >= len(bracket):
                    winners.append(bracket[index])
                    continue
                winners.append(head_to_head_winner(bracket[index], bracket[index + 1], teams, rng))
            for winner in winners:
                counts[winner][next_stage] += 1
            round_teams = winners

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
    if weight == 0:
        impact = "不入模型"
        tone = "muted"
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
        "applied": len([event for event in EVENTS if SOURCE_WEIGHTS[event.source_level] > 0 and event.team is not None]),
        "ignored": len([event for event in EVENTS if SOURCE_WEIGHTS[event.source_level] == 0]),
    }


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
        scenario = simulate_tournament(teams, outcome, simulation_count)
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


def build_match_prediction(simulation_count: int = SIMULATION_COUNT) -> dict[str, object]:
    teams = apply_event_adjustments()
    home_key, away_key = CURRENT_MATCH
    current_fixture = next(fixture for fixture in FIXTURES if (fixture.home, fixture.away) == CURRENT_MATCH)
    probabilities = win_draw_loss(home_key, away_key, teams)
    distribution = score_distribution(home_key, away_key, teams)
    base_tournament = simulate_tournament(teams, simulation_count=simulation_count)

    score_outcomes = [
        {
            "score": item["score"],
            "probability": round(float(item["probability"]) * 100, 1),
            "note": ["双方基础强度接近", "边路优势可能放大", "低比分胜局仍有空间"][index],
            "tone": tone_for_probability(index),
        }
        for index, item in enumerate(distribution[:3])
    ]

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
        "scoreOutcomes": score_outcomes,
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
