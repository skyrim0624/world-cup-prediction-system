from __future__ import annotations

from pathlib import Path
from typing import Any

from . import data as data_state
from .model import event_summary, event_to_news_item
from .snapshot import read_prediction_snapshot


def fixture_status_counts() -> dict[str, int]:
    return {
        "scheduled": len([fixture for fixture in data_state.FIXTURES if fixture.status == "scheduled"]),
        "live": len([fixture for fixture in data_state.FIXTURES if fixture.status == "live"]),
        "finished": len([fixture for fixture in data_state.FIXTURES if fixture.status == "finished"]),
    }


def review_queue(limit: int = 8) -> list[dict[str, Any]]:
    items = []
    for event in data_state.EVENTS:
        if event.action != "watch":
            continue
        news_item = event_to_news_item(event)
        items.append(
            {
                **news_item,
                "id": event.id,
                "team": event.team,
                "source": event.source,
                "sourceLevel": event.source_level,
                "status": event.status,
                "action": event.action,
                "factor": event.factor,
                "url": event.url,
            }
        )
        if len(items) >= limit:
            break
    return items


def build_admin_overview(snapshot_path: Path) -> dict[str, Any]:
    snapshot = read_prediction_snapshot(snapshot_path)
    return {
        "fixtureStatus": fixture_status_counts(),
        "eventSummary": event_summary(),
        "rawNewsCount": len(data_state.RAW_NEWS_ITEMS),
        "reviewQueue": review_queue(),
        "latestSnapshot": snapshot.get("snapshotMeta") if snapshot else None,
        "operations": {
            "dailyUpdateCommand": "npm run daily:update",
            "snapshotRebuildEndpoint": "/api/snapshot/rebuild",
            "rawNewsEndpoint": "/api/raw-news",
            "eventReviewEndpoint": "/api/events/review",
            "liveScoreEndpoint": "/api/fixtures/live",
            "resultEndpoint": "/api/fixtures/result",
        },
    }
