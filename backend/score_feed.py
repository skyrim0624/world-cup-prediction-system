from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .io_utils import write_json_atomic


def parse_score(value: Any) -> int:
    if value in (None, ""):
        return 0
    return int(value)


def parse_optional_score(value: Any) -> int | None:
    if value in (None, ""):
        return None
    return int(value)


def event_status(event: dict[str, Any], competition: dict[str, Any]) -> str:
    status = competition.get("status") or event.get("status") or {}
    status_type = status.get("type") or {}
    state = str(status_type.get("state") or "").lower()
    completed = bool(status_type.get("completed"))
    if completed or state == "post":
        return "finished"
    if state == "in":
        return "live"
    return "scheduled"


def parse_espn_scoreboard(feed_text: str) -> list[dict[str, Any]]:
    payload = json.loads(feed_text)
    rows: list[dict[str, Any]] = []
    for event in payload.get("events", []):
        competitions = event.get("competitions") or []
        if not competitions:
            continue
        competition = competitions[0]
        competitors = competition.get("competitors") or []
        by_side = {competitor.get("homeAway"): competitor for competitor in competitors}
        home = by_side.get("home")
        away = by_side.get("away")
        if home is None or away is None:
            continue
        rows.append(
            {
                "sourceEventId": event.get("id"),
                "homeCode": str((home.get("team") or {}).get("abbreviation") or "").upper(),
                "awayCode": str((away.get("team") or {}).get("abbreviation") or "").upper(),
                "homeScore": parse_score(home.get("score")),
                "awayScore": parse_score(away.get("score")),
                "status": event_status(event, competition),
            }
        )
    return rows


def has_nested_key(value: Any, keywords: tuple[str, ...]) -> bool:
    if isinstance(value, dict):
        for key, child in value.items():
            lowered = str(key).lower()
            if any(keyword in lowered for keyword in keywords):
                return True
            if has_nested_key(child, keywords):
                return True
    if isinstance(value, list):
        return any(has_nested_key(child, keywords) for child in value)
    return False


def fifa_match_status(match: dict[str, Any], home_score: int | None, away_score: int | None) -> str:
    if home_score is None or away_score is None:
        return "scheduled"

    match_status = "" if match.get("MatchStatus") is None else str(match.get("MatchStatus"))
    result_type = "" if match.get("ResultType") is None else str(match.get("ResultType"))
    if match_status == "0" or result_type not in {"", "0"}:
        return "finished"
    if match.get("MatchTime") or match.get("Minute") or match.get("Period"):
        return "live"
    return "scheduled"


def fifa_match_metadata(match: dict[str, Any]) -> dict[str, bool]:
    home = match.get("Home") or {}
    away = match.get("Away") or {}
    return {
        "lineupObserved": bool(home.get("Tactics") or away.get("Tactics") or has_nested_key(match, ("lineup", "starting"))),
        "disciplineObserved": has_nested_key(match, ("card", "booking", "discipline")),
        "weatherObserved": bool(match.get("Weather")),
        "stadiumObserved": bool(match.get("Stadium")),
    }


def parse_fifa_calendar_matches(feed_text: str) -> list[dict[str, Any]]:
    payload = json.loads(feed_text)
    rows: list[dict[str, Any]] = []
    for match in payload.get("Results", []):
        home = match.get("Home") or {}
        away = match.get("Away") or {}
        home_score = parse_optional_score(match.get("HomeTeamScore", home.get("Score")))
        away_score = parse_optional_score(match.get("AwayTeamScore", away.get("Score")))
        rows.append(
            {
                "sourceEventId": str(match.get("IdMatch") or ""),
                "matchNumber": match.get("MatchNumber"),
                "homeCode": str(home.get("Abbreviation") or "").upper(),
                "awayCode": str(away.get("Abbreviation") or "").upper(),
                "homeScore": home_score,
                "awayScore": away_score,
                "status": fifa_match_status(match, home_score, away_score),
                "metadata": fifa_match_metadata(match),
            }
        )
    return rows


def parse_score_source(content: str, format_name: str) -> list[dict[str, Any]]:
    if format_name == "fifa_calendar_matches":
        return parse_fifa_calendar_matches(content)
    if format_name == "espn_scoreboard":
        return parse_espn_scoreboard(content)
    raise ValueError(f"不支持的赛果源格式: {format_name}")


def fixture_matches(fixture: dict[str, Any], home: str, away: str) -> bool:
    return fixture.get("home") == home and fixture.get("away") == away


def fixture_matches_match_number(fixture: dict[str, Any], row: dict[str, Any]) -> bool:
    match_number = row.get("matchNumber")
    return match_number is not None and fixture.get("match_no") == match_number


def update_fixture_from_score(
    fixture: dict[str, Any],
    status: str,
    home_score: int | None,
    away_score: int | None,
) -> str:
    if fixture.get("status") == "finished" and status != "finished":
        return "stale"
    fixture["status"] = status
    fixture["home_score"] = home_score
    fixture["away_score"] = away_score
    return "updated"


OBSERVED_METADATA_KEYS = {
    "lineupObserved": "lineupsObserved",
    "disciplineObserved": "disciplineObserved",
    "weatherObserved": "weatherObserved",
    "stadiumObserved": "stadiumsObserved",
}


def apply_score_source_updates(
    fixtures_path: Path,
    source_payloads: list[dict[str, Any]],
    code_to_team: dict[str, str],
) -> dict[str, Any]:
    fixtures = json.loads(fixtures_path.read_text(encoding="utf-8"))
    report = {
        "updated": 0,
        "finished": 0,
        "live": 0,
        "skipped": 0,
        "unknownTeams": 0,
        "lineupsObserved": 0,
        "disciplineObserved": 0,
        "weatherObserved": 0,
        "stadiumsObserved": 0,
        "staleSkipped": 0,
        "standingsSource": "computed_from_local_fixtures",
        "items": [],
    }
    official_fifa_updated = False

    for source_payload in source_payloads:
        parsed_rows = parse_score_source(source_payload["content"], source_payload["format"])
        item_report = {
            "source": source_payload.get("source"),
            "format": source_payload["format"],
            "url": source_payload.get("url"),
            "input": source_payload.get("input"),
            "parsed": len(parsed_rows),
            "updated": 0,
            "skipped": 0,
            "unknownTeams": 0,
            "lineupsObserved": 0,
            "disciplineObserved": 0,
            "weatherObserved": 0,
            "stadiumsObserved": 0,
            "staleSkipped": 0,
        }
        for row in parsed_rows:
            metadata = row.get("metadata") or {}
            for metadata_key, report_key in OBSERVED_METADATA_KEYS.items():
                if metadata.get(metadata_key):
                    report[report_key] += 1
                    item_report[report_key] += 1

            status = row["status"]
            if status not in {"finished", "live"}:
                report["skipped"] += 1
                item_report["skipped"] += 1
                continue

            home = code_to_team.get(row["homeCode"])
            away = code_to_team.get(row["awayCode"])
            if home is None or away is None:
                report["unknownTeams"] += 1
                item_report["unknownTeams"] += 1
                continue

            matched = False
            stale_skipped = False
            for fixture in fixtures:
                if fixture_matches_match_number(fixture, row) and fixture_matches(fixture, home, away):
                    stale_skipped = update_fixture_from_score(fixture, status, row["homeScore"], row["awayScore"]) == "stale"
                    matched = True
                    break
                if fixture_matches_match_number(fixture, row) and fixture_matches(fixture, away, home):
                    stale_skipped = update_fixture_from_score(fixture, status, row["awayScore"], row["homeScore"]) == "stale"
                    matched = True
                    break
            if not matched:
                for fixture in fixtures:
                    if fixture_matches(fixture, home, away):
                        stale_skipped = update_fixture_from_score(fixture, status, row["homeScore"], row["awayScore"]) == "stale"
                        matched = True
                        break
                    if fixture_matches(fixture, away, home):
                        stale_skipped = update_fixture_from_score(fixture, status, row["awayScore"], row["homeScore"]) == "stale"
                        matched = True
                        break

            if not matched:
                report["skipped"] += 1
                item_report["skipped"] += 1
                continue
            if stale_skipped:
                report["staleSkipped"] += 1
                item_report["staleSkipped"] += 1
                continue

            report["updated"] += 1
            report[status] += 1
            item_report["updated"] += 1
            if source_payload.get("source") == "fifa":
                official_fifa_updated = True

        report["items"].append(item_report)

    if official_fifa_updated:
        report["standingsSource"] = "computed_from_official_fifa_results"

    if report["updated"]:
        write_json_atomic(fixtures_path, fixtures)
    return report
