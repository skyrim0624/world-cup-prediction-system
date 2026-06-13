from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def record_fixture_result(
    path: Path,
    home: str,
    away: str,
    home_score: int,
    away_score: int,
) -> dict[str, Any]:
    return record_fixture_score(path, home, away, home_score, away_score, "finished")


def record_fixture_live_score(
    path: Path,
    home: str,
    away: str,
    home_score: int,
    away_score: int,
) -> dict[str, Any]:
    return record_fixture_score(path, home, away, home_score, away_score, "live")


def record_fixture_score(
    path: Path,
    home: str,
    away: str,
    home_score: int,
    away_score: int,
    status: str,
) -> dict[str, Any]:
    if home_score < 0 or away_score < 0:
        raise ValueError("比分不能为负数")

    rows = json.loads(path.read_text(encoding="utf-8"))
    for row in rows:
        if row["home"] != home or row["away"] != away:
            continue
        row["status"] = status
        row["home_score"] = home_score
        row["away_score"] = away_score
        path.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return row
    raise ValueError(f"找不到赛程: {home} vs {away}")
