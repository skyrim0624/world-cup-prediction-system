from __future__ import annotations

import argparse
import csv
import io
import json
from collections import defaultdict
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

DEFAULT_SOURCE_URL = "https://raw.githubusercontent.com/martj42/international_results/master/results.csv"
DEFAULT_DATA_DIR = Path("backend/data_files")
DEFAULT_OUTPUT_PATH = DEFAULT_DATA_DIR / "team-match-history.json"
DEFAULT_TEAM_MAP_PATH = DEFAULT_DATA_DIR / "team-name-map.json"
DEFAULT_SINCE = "2018-01-01"
REQUEST_HEADERS = {"User-Agent": "world-cup-prediction-system/0.1"}

MAJOR_TOURNAMENT_KEYWORDS = (
    "FIFA World Cup",
    "UEFA Euro",
    "Copa América",
    "CONCACAF Gold Cup",
    "African Cup of Nations",
    "AFC Asian Cup",
    "Oceania Nations Cup",
)
QUALIFIER_KEYWORDS = ("qualification", "qualifier", "UEFA Nations League", "CONCACAF Nations League")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="导入公开 CC0 国际男足历史赛果，生成 48 队历史模型数据。")
    parser.add_argument("--source-url", default=DEFAULT_SOURCE_URL)
    parser.add_argument("--team-map", type=Path, default=DEFAULT_TEAM_MAP_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--since", default=DEFAULT_SINCE)
    parser.add_argument("--until", default=date.today().isoformat())
    return parser.parse_args()


def read_csv_rows(source_url: str) -> list[dict[str, str]]:
    request = Request(source_url, headers=REQUEST_HEADERS)
    with urlopen(request, timeout=45) as response:
        content = response.read().decode("utf-8")
    return list(csv.DictReader(io.StringIO(content)))


def has_score(row: dict[str, str]) -> bool:
    return row.get("home_score") not in {None, "", "NA"} and row.get("away_score") not in {None, "", "NA"}


def match_result(home_score: int, away_score: int) -> tuple[float, float]:
    if home_score > away_score:
        return 1.0, 0.0
    if home_score < away_score:
        return 0.0, 1.0
    return 0.5, 0.5


def tournament_k(row: dict[str, str]) -> float:
    tournament = row.get("tournament", "")
    if any(keyword in tournament for keyword in MAJOR_TOURNAMENT_KEYWORDS):
        return 34.0
    lowered = tournament.lower()
    if any(keyword.lower() in lowered for keyword in QUALIFIER_KEYWORDS):
        return 24.0
    if tournament == "Friendly":
        return 12.0
    return 18.0


def expected_score(rating_a: float, rating_b: float, neutral: bool) -> float:
    home_advantage = 0.0 if neutral else 55.0
    return 1 / (1 + 10 ** (-((rating_a + home_advantage) - rating_b) / 400))


def update_elo(ratings: dict[str, float], row: dict[str, str]) -> dict[str, float]:
    home = row["home_team"]
    away = row["away_team"]
    home_rating = ratings[home]
    away_rating = ratings[away]
    home_score = int(row["home_score"])
    away_score = int(row["away_score"])
    home_result, away_result = match_result(home_score, away_score)
    home_expected = expected_score(home_rating, away_rating, row.get("neutral") == "TRUE")
    margin = abs(home_score - away_score)
    margin_multiplier = 1.0 + min(2.0, margin) * 0.12
    k = tournament_k(row) * margin_multiplier
    delta = k * (home_result - home_expected)
    ratings[home] = home_rating + delta
    ratings[away] = away_rating - delta
    return {
        "homeEloBefore": round(home_rating, 1),
        "awayEloBefore": round(away_rating, 1),
        "homeEloAfter": round(ratings[home], 1),
        "awayEloAfter": round(ratings[away], 1),
    }


def scored_rows_with_elos(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    ratings: defaultdict[str, float] = defaultdict(lambda: 1500.0)
    enriched = []
    for row in sorted((row for row in rows if has_score(row)), key=lambda item: item["date"]):
        elo = update_elo(ratings, row)
        enriched.append({**row, **elo})
    return enriched


def build_history_payload(
    rows: list[dict[str, Any]],
    team_map: dict[str, str],
    source_url: str,
    since: str,
    until: str,
) -> dict[str, Any]:
    dataset_to_key = {name: key for key, name in team_map.items()}
    selected_names = set(dataset_to_key)
    filtered_matches = []
    team_counts = {key: 0 for key in team_map}
    latest_elos = {key: None for key in team_map}
    latest_elo_dates = {key: None for key in team_map}
    since_date = datetime.fromisoformat(since).date()
    until_date = datetime.fromisoformat(until).date()

    for row in rows:
        match_date = datetime.fromisoformat(row["date"]).date()
        if match_date > until_date:
            continue
        home_key = dataset_to_key.get(row["home_team"])
        away_key = dataset_to_key.get(row["away_team"])
        if home_key:
            latest_elos[home_key] = row["homeEloAfter"]
            latest_elo_dates[home_key] = row["date"]
        if away_key:
            latest_elos[away_key] = row["awayEloAfter"]
            latest_elo_dates[away_key] = row["date"]
        if match_date < since_date:
            continue
        if row["home_team"] not in selected_names and row["away_team"] not in selected_names:
            continue
        record = {
            "date": row["date"],
            "home": home_key,
            "away": away_key,
            "homeName": row["home_team"],
            "awayName": row["away_team"],
            "homeScore": int(row["home_score"]),
            "awayScore": int(row["away_score"]),
            "tournament": row["tournament"],
            "city": row["city"],
            "country": row["country"],
            "neutral": row["neutral"] == "TRUE",
            "homeEloBefore": row["homeEloBefore"],
            "awayEloBefore": row["awayEloBefore"],
        }
        filtered_matches.append(record)
        if home_key:
            team_counts[home_key] += 1
        if away_key:
            team_counts[away_key] += 1

    return {
        "meta": {
            "source": "martj42/international_results",
            "sourceUrl": source_url,
            "license": "CC0-1.0",
            "retrievedAt": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "since": since,
            "until": until,
            "scoredMatches": len(filtered_matches),
            "matchedTeams": len([key for key, count in team_counts.items() if count > 0]),
            "notes": "Filtered to matches involving the 48 configured World Cup teams; rows with NA scores are excluded.",
        },
        "teams": {
            key: {
                "datasetName": name,
                "scoredMatches": team_counts[key],
                "latestElo": latest_elos[key],
                "latestEloDate": latest_elo_dates[key],
            }
            for key, name in team_map.items()
        },
        "matches": filtered_matches,
    }


def main() -> None:
    args = parse_args()
    team_map = json.loads(args.team_map.read_text(encoding="utf-8"))
    rows = read_csv_rows(args.source_url)
    enriched_rows = scored_rows_with_elos(rows)
    payload = build_history_payload(enriched_rows, team_map, args.source_url, args.since, args.until)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"已导入历史赛果: {payload['meta']['scoredMatches']} 场，"
        f"{payload['meta']['matchedTeams']} 支球队，来源 {payload['meta']['source']} ({payload['meta']['license']})"
    )


if __name__ == "__main__":
    main()
