from __future__ import annotations

from time import monotonic

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from . import data as data_state
from .admin import build_admin_overview
from .event_review import RAW_NEWS_PATH, review_raw_news_item
from .fixture_update import record_fixture_live_score, record_fixture_result
from .model import (
    SIMULATION_COUNT,
    build_match_detail,
    build_match_prediction,
    build_upcoming_match_predictions,
    event_summary,
    event_to_news_item,
    reload_model_data,
)
from .news_ingest import append_raw_news_item
from .snapshot import DEFAULT_SNAPSHOT_PATH, read_prediction_snapshot, write_prediction_snapshot


app = FastAPI(title="World Cup Prediction MVP")
PREDICTION_CACHE_TTL_SECONDS = 15
prediction_cache: dict[int, tuple[float, dict[str, object]]] = {}
review_data_path = RAW_NEWS_PATH
snapshot_data_path = DEFAULT_SNAPSHOT_PATH
fixtures_data_path = data_state.DATA_DIR / "fixtures.json"


class EventReviewRequest(BaseModel):
    id: str
    status: str
    team: str | None = None


class SnapshotRebuildRequest(BaseModel):
    simulations: int = SIMULATION_COUNT


class RawNewsCreateRequest(BaseModel):
    id: str
    title: str
    summary: str
    source: str
    team: str | None = None
    status: str
    publishedAt: str
    url: str


class FixtureResultRequest(BaseModel):
    home: str
    away: str
    homeScore: int
    awayScore: int


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://127.0.0.1:5174", "http://localhost:5173", "http://localhost:5174"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/match-prediction")
def match_prediction(
    simulations: int = Query(SIMULATION_COUNT, ge=1_000, le=50_000),
    use_snapshot: bool = Query(True, alias="useSnapshot"),
) -> dict[str, object]:
    if use_snapshot:
        snapshot = read_prediction_snapshot(snapshot_data_path)
        if snapshot is not None:
            return snapshot
    now = monotonic()
    cached = prediction_cache.get(simulations)
    if cached and now - cached[0] < PREDICTION_CACHE_TTL_SECONDS:
        return cached[1]
    prediction = build_match_prediction(simulations)
    prediction_cache[simulations] = (now, prediction)
    return prediction


@app.get("/api/model-status")
def model_status() -> dict[str, object]:
    return {
        "dataset": data_state.DATASET_META,
        "simulationCount": SIMULATION_COUNT,
        "lockedResults": len([fixture for fixture in data_state.FIXTURES if fixture.status == "finished"]),
        "liveMatches": len([fixture for fixture in data_state.FIXTURES if fixture.status == "live"]),
        "eventSummary": event_summary(),
        "knownGaps": [
            "官方 48 队名单和真实分组尚未替换当前槽位数据",
            "新闻抓取仍由本地 raw-news JSON 承接，暂未接外部定时任务",
            "运营后台尚未接登录权限、完整新闻录入和支付权限",
        ],
    }


@app.get("/api/admin/overview")
def admin_overview() -> dict[str, object]:
    return build_admin_overview(snapshot_data_path)


@app.get("/api/upcoming-matches")
def upcoming_matches(limit: int = Query(12, ge=1, le=72)) -> dict[str, object]:
    return build_upcoming_match_predictions(limit)


@app.get("/api/match-detail")
def match_detail(
    home: str,
    away: str,
    simulations: int = Query(1200, ge=1_000, le=50_000),
) -> dict[str, object]:
    try:
        return build_match_detail(home, away, simulations)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.get("/api/events")
def events() -> dict[str, object]:
    items = []
    for event in data_state.EVENTS:
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
                "direction": event.direction,
                "strength": event.strength,
                "url": event.url,
            }
        )
    return {
        "summary": event_summary(),
        "rawNewsCount": len(data_state.RAW_NEWS_ITEMS),
        "items": items,
    }


@app.post("/api/events/review")
def review_event(request: EventReviewRequest) -> dict[str, object]:
    try:
        updated = review_raw_news_item(review_data_path, request.id, request.status, request.team)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    reload_model_data(review_data_path, fixtures_data_path)
    prediction_cache.clear()
    return {
        "item": updated,
        "requiresSnapshotRefresh": True,
    }


@app.post("/api/raw-news")
def create_raw_news(request: RawNewsCreateRequest) -> dict[str, object]:
    if request.source not in data_state.NEWS_SOURCES:
        raise HTTPException(status_code=400, detail=f"未知新闻来源: {request.source}")
    if request.team is not None and request.team not in data_state.TEAM_PROFILES:
        raise HTTPException(status_code=400, detail=f"未知球队: {request.team}")

    item = {
        "id": request.id,
        "title": request.title,
        "summary": request.summary,
        "source": request.source,
        "team": request.team,
        "status": request.status,
        "published_at": request.publishedAt,
        "url": request.url,
    }
    try:
        created = append_raw_news_item(review_data_path, item)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    reload_model_data(review_data_path, fixtures_data_path)
    prediction_cache.clear()
    return {
        "item": created,
        "requiresReview": True,
    }


@app.post("/api/snapshot/rebuild")
def rebuild_snapshot(request: SnapshotRebuildRequest) -> dict[str, object]:
    reload_model_data(review_data_path, fixtures_data_path)
    payload = write_prediction_snapshot(snapshot_data_path, request.simulations)
    prediction_cache.clear()
    return payload


@app.post("/api/fixtures/result")
def update_fixture_result(request: FixtureResultRequest) -> dict[str, object]:
    if request.home not in data_state.TEAM_PROFILES or request.away not in data_state.TEAM_PROFILES:
        raise HTTPException(status_code=400, detail="赛果包含未知球队")
    try:
        fixture = record_fixture_result(
            fixtures_data_path,
            request.home,
            request.away,
            request.homeScore,
            request.awayScore,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    reload_model_data(review_data_path, fixtures_data_path)
    prediction_cache.clear()
    return {
        "fixture": fixture,
        "requiresSnapshotRefresh": True,
    }


@app.post("/api/fixtures/live")
def update_fixture_live_score(request: FixtureResultRequest) -> dict[str, object]:
    if request.home not in data_state.TEAM_PROFILES or request.away not in data_state.TEAM_PROFILES:
        raise HTTPException(status_code=400, detail="进行中比分包含未知球队")
    try:
        fixture = record_fixture_live_score(
            fixtures_data_path,
            request.home,
            request.away,
            request.homeScore,
            request.awayScore,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    reload_model_data(review_data_path, fixtures_data_path)
    prediction_cache.clear()
    return {
        "fixture": fixture,
        "requiresSnapshotRefresh": True,
    }
