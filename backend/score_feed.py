from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def parse_score(value: Any) -> int:
    if value in (None, ""):
        return 0
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


def parse_score_source(content: str, format_name: str) -> list[dict[str, Any]]:
    if format_name == "espn_scoreboard":
        return parse_espn_scoreboard(content)
    raise ValueError(f"不支持的赛果源格式: {format_name}")


def fixture_matches(fixture: dict[str, Any], home: str, away: str) -> bool:
    return fixture.get("home") == home and fixture.get("away") == away


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
        "items": [],
    }

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
        }
        for row in parsed_rows:
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
            for fixture in fixtures:
                if fixture_matches(fixture, home, away):
                    fixture["status"] = status
                    fixture["home_score"] = row["homeScore"]
                    fixture["away_score"] = row["awayScore"]
                    matched = True
                    break
                if fixture_matches(fixture, away, home):
                    fixture["status"] = status
                    fixture["home_score"] = row["awayScore"]
                    fixture["away_score"] = row["homeScore"]
                    matched = True
                    break

            if not matched:
                report["skipped"] += 1
                item_report["skipped"] += 1
                continue

            report["updated"] += 1
            report[status] += 1
            item_report["updated"] += 1

        report["items"].append(item_report)

    if report["updated"]:
        fixtures_path.write_text(json.dumps(fixtures, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report
