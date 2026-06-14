from __future__ import annotations

from time import monotonic

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from . import data as data_state
from .access import build_access_options, build_access_policy
from .admin import build_admin_overview
from .admin_audit import AUDIT_LOG_PATH, append_admin_audit
from .admin_security import verify_admin_token
from .data_import import apply_tournament_data_import, restore_tournament_backup
from .daily_update import DEFAULT_DAILY_STATUS_PATH
from .event_review import RAW_NEWS_PATH, review_raw_news_item
from .fixture_update import record_fixture_live_score, record_fixture_result
from .model import (
    FinishedMatchPredictionError,
    SIMULATION_COUNT,
    build_finished_match_records,
    build_match_detail,
    build_match_prediction,
    build_upcoming_match_predictions,
    event_summary,
    event_to_news_item,
    reload_model_data,
)
from .news_ingest import append_raw_news_item
from .payments import build_order_access_decision, build_payment_config, create_payment_order, get_payment_order
from .snapshot import DEFAULT_SNAPSHOT_PATH, build_probability_movers, read_prediction_snapshot, write_prediction_snapshot


app = FastAPI(title="World Cup Prediction MVP")
PREDICTION_CACHE_TTL_SECONDS = 15
prediction_cache: dict[int, tuple[float, dict[str, object]]] = {}
review_data_path = RAW_NEWS_PATH
snapshot_data_path = DEFAULT_SNAPSHOT_PATH
fixtures_data_path = data_state.DATA_DIR / "fixtures.json"
audit_log_path = AUDIT_LOG_PATH
daily_status_path = DEFAULT_DAILY_STATUS_PATH
runtime_data_dir = data_state.DATA_DIR
tournament_backup_dir = data_state.DATA_DIR / "backups"
payment_orders_path = data_state.DATA_DIR / "payment-orders.json"


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


class TournamentRollbackRequest(BaseModel):
    backupId: str


class PaymentOrderCreateRequest(BaseModel):
    productKey: str
    provider: str


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://127.0.0.1:5174", "http://localhost:5173", "http://localhost:5174"],
    allow_origin_regex=r"^http://(127\.0\.0\.1|localhost):517[0-9]$",
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
    prediction["dailyMovers"] = build_probability_movers(prediction, None)
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
            "小组赛真实赛程已导入，淘汰赛具体球队对阵仍需根据小组赛结果动态生成",
            "真实新闻 Feed 配置已接入，赛果源和 GitHub Actions 定时日更已补齐，仍需客户授权接口替换生产源",
            "后台权限仍为轻量 token，支付已有客户接口框架和订单访问判断，但暂未接用户账号、角色和正式数据库订单表",
        ],
    }


@app.get("/api/access-options")
def access_options() -> dict[str, object]:
    return build_access_options(payment_configured=False)


@app.get("/api/access-policy")
def access_policy() -> dict[str, object]:
    return build_access_policy(payment_configured=False)


@app.get("/api/access-decision")
def access_decision(orderId: str, contentKey: str) -> dict[str, object]:
    return build_order_access_decision(orderId, contentKey, payment_orders_path)


@app.get("/api/payments/config")
def payment_config() -> dict[str, object]:
    return build_payment_config()


@app.post("/api/payments/orders")
def create_order(request: PaymentOrderCreateRequest) -> dict[str, object]:
    try:
        return create_payment_order(request.productKey, request.provider, storage_path=payment_orders_path)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.get("/api/payments/orders/{order_id}")
def payment_order(order_id: str) -> dict[str, object]:
    try:
        return get_payment_order(order_id, payment_orders_path)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="支付订单不存在") from error


@app.get("/api/admin/overview")
def admin_overview() -> dict[str, object]:
    return build_admin_overview(snapshot_data_path, audit_log_path, daily_status_path, tournament_backup_dir)


@app.get("/api/upcoming-matches")
def upcoming_matches(limit: int = Query(12, ge=1, le=72)) -> dict[str, object]:
    return build_upcoming_match_predictions(limit)


@app.get("/api/finished-matches")
def finished_matches(limit: int = Query(12, ge=1, le=72)) -> dict[str, object]:
    return build_finished_match_records(limit)


@app.get("/api/match-detail")
def match_detail(
    home: str,
    away: str,
    simulations: int = Query(1200, ge=1_000, le=50_000),
) -> dict[str, object]:
    try:
        return build_match_detail(home, away, simulations)
    except FinishedMatchPredictionError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
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
def review_event(request: EventReviewRequest, _: None = Depends(verify_admin_token)) -> dict[str, object]:
    try:
        updated = review_raw_news_item(review_data_path, request.id, request.status, request.team)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    append_admin_audit("event:review", request.id, {"status": request.status, "team": request.team}, audit_log_path)
    reload_model_data(review_data_path, fixtures_data_path)
    prediction_cache.clear()
    return {
        "item": updated,
        "requiresSnapshotRefresh": True,
    }


@app.post("/api/raw-news")
def create_raw_news(request: RawNewsCreateRequest, _: None = Depends(verify_admin_token)) -> dict[str, object]:
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
    append_admin_audit("raw-news:create", request.id, {"source": request.source, "team": request.team}, audit_log_path)
    reload_model_data(review_data_path, fixtures_data_path)
    prediction_cache.clear()
    return {
        "item": created,
        "requiresReview": True,
    }


@app.post("/api/snapshot/rebuild")
def rebuild_snapshot(request: SnapshotRebuildRequest, _: None = Depends(verify_admin_token)) -> dict[str, object]:
    reload_model_data(review_data_path, fixtures_data_path)
    payload = write_prediction_snapshot(snapshot_data_path, request.simulations)
    append_admin_audit("snapshot:rebuild", str(snapshot_data_path), {"simulations": request.simulations}, audit_log_path)
    prediction_cache.clear()
    return payload


@app.post("/api/fixtures/result")
def update_fixture_result(request: FixtureResultRequest, _: None = Depends(verify_admin_token)) -> dict[str, object]:
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
    append_admin_audit(
        "fixture:result",
        f"{request.home}-{request.away}",
        {"homeScore": request.homeScore, "awayScore": request.awayScore},
        audit_log_path,
    )
    reload_model_data(review_data_path, fixtures_data_path)
    prediction_cache.clear()
    return {
        "fixture": fixture,
        "requiresSnapshotRefresh": True,
    }


@app.post("/api/fixtures/live")
def update_fixture_live_score(request: FixtureResultRequest, _: None = Depends(verify_admin_token)) -> dict[str, object]:
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
    append_admin_audit(
        "fixture:live",
        f"{request.home}-{request.away}",
        {"homeScore": request.homeScore, "awayScore": request.awayScore},
        audit_log_path,
    )
    reload_model_data(review_data_path, fixtures_data_path)
    prediction_cache.clear()
    return {
        "fixture": fixture,
        "requiresSnapshotRefresh": True,
    }


@app.post("/api/admin/tournament-data/import")
def import_tournament_data(payload: dict[str, object], _: None = Depends(verify_admin_token)) -> dict[str, object]:
    try:
        result = apply_tournament_data_import(runtime_data_dir, tournament_backup_dir, payload)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    reload_model_data(review_data_path, runtime_data_dir / "fixtures.json", runtime_data_dir / "teams.json")
    prediction_cache.clear()
    append_admin_audit(
        "tournament-data:import",
        str(result["source"]),
        {"teamCount": result["teamCount"], "fixtureCount": result["fixtureCount"], "backupDir": result["backupDir"]},
        audit_log_path,
    )
    return result


@app.post("/api/admin/tournament-data/rollback")
def rollback_tournament_data(request: TournamentRollbackRequest, _: None = Depends(verify_admin_token)) -> dict[str, object]:
    try:
        result = restore_tournament_backup(runtime_data_dir, tournament_backup_dir, request.backupId)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    reload_model_data(review_data_path, runtime_data_dir / "fixtures.json", runtime_data_dir / "teams.json")
    prediction_cache.clear()
    append_admin_audit(
        "tournament-data:rollback",
        request.backupId,
        {"sourceBackupDir": result["sourceBackupDir"], "currentBackupDir": result["currentBackupDir"]},
        audit_log_path,
    )
    return result
