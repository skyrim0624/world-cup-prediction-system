from __future__ import annotations

from pathlib import Path
from typing import Any

from . import data as data_state
from .admin_audit import read_recent_admin_audit
from .admin_security import admin_auth_required
from .daily_update import read_daily_update_status
from .data_import import list_tournament_backups
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


def build_admin_overview(
    snapshot_path: Path,
    audit_path: Path | None = None,
    daily_status_path: Path | None = None,
    tournament_backup_root: Path | None = None,
) -> dict[str, Any]:
    snapshot = read_prediction_snapshot(snapshot_path)
    dataset = data_state.DATASET_META
    return {
        "fixtureStatus": fixture_status_counts(),
        "eventSummary": event_summary(),
        "datasetHealth": {
            "teamCount": dataset.get("teamCount", 0),
            "fixtureCount": dataset.get("fixtureCount", 0),
            "placeholderSlots": dataset.get("placeholderSlots", 0),
            "isOfficialDataReady": dataset.get("placeholderSlots", 0) == 0 and dataset.get("teamCount", 0) == 48,
        },
        "rawNewsCount": len(data_state.RAW_NEWS_ITEMS),
        "reviewQueue": review_queue(),
        "latestSnapshot": snapshot.get("snapshotMeta") if snapshot else None,
        "dailyUpdateStatus": read_daily_update_status(daily_status_path) if daily_status_path else read_daily_update_status(),
        "tournamentBackups": list_tournament_backups(tournament_backup_root) if tournament_backup_root else [],
        "authRequired": admin_auth_required(),
        "recentAudit": read_recent_admin_audit(audit_path) if audit_path else read_recent_admin_audit(),
        "operations": {
            "dailyUpdateCommand": "npm run daily:update",
            "snapshotRebuildEndpoint": "/api/snapshot/rebuild",
            "rawNewsEndpoint": "/api/raw-news",
            "eventReviewEndpoint": "/api/events/review",
            "liveScoreEndpoint": "/api/fixtures/live",
            "resultEndpoint": "/api/fixtures/result",
            "tournamentImportEndpoint": "/api/admin/tournament-data/import",
            "tournamentRollbackEndpoint": "/api/admin/tournament-data/rollback",
        },
    }
