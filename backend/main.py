from __future__ import annotations

import os
from hmac import compare_digest
from pathlib import Path
from time import monotonic

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import data as data_state
from .access import build_access_options, build_access_policy
from .admin import build_admin_overview, build_prediction_run_monitor
from .admin_audit import AUDIT_LOG_PATH, append_admin_audit
from .admin_security import resolve_admin_token, verify_admin_token
from .data_import import apply_tournament_data_import, restore_tournament_backup
from .daily_update import DEFAULT_DAILY_STATUS_PATH
from .event_review import RAW_NEWS_PATH, review_raw_news_item
from .fixture_update import record_fixture_live_score, record_fixture_result
from .model import (
    FinishedMatchPredictionError,
    SIMULATION_COUNT,
    build_finished_match_review,
    build_finished_match_records,
    build_match_detail,
    build_match_prediction,
    build_public_finished_match_records,
    build_public_match_summary,
    build_public_upcoming_match_list,
    build_upcoming_match_predictions,
    event_summary,
    event_to_news_item,
    reload_model_data,
)
from .news_ingest import append_raw_news_item
from .payments import build_order_access_decision, build_payment_config, create_payment_order, get_payment_order, handle_payment_notification, refresh_payment_order_status
from .production_health import build_production_readiness
from .snapshot import DEFAULT_SNAPSHOT_PATH, build_probability_movers, read_prediction_snapshot, write_prediction_snapshot


app = FastAPI(title="World Cup Prediction MVP")
PROJECT_ROOT = Path(__file__).resolve().parents[1]
STATIC_DIST_DIR = PROJECT_ROOT / "dist"
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
    contentKey: str | None = None
    matchKey: str | None = None
    homeTeam: str | None = None
    awayTeam: str | None = None
    homeName: str | None = None
    awayName: str | None = None
    wechatOpenId: str | None = None


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://localhost:5173",
        "http://localhost:5174",
        "https://world-cup-prediction-system.pages.dev",
        "https://world-cup-prediction-admin.pages.dev",
        "https://zhugejunshi.com",
        "https://www.zhugejunshi.com",
    ],
    allow_origin_regex=r"^(http://(127\.0\.0\.1|localhost):51[0-9]{2}|https://[a-z0-9-]+\.(world-cup-prediction-system|world-cup-prediction-admin)\.pages\.dev|https://[a-z0-9-]+\.zhugejunshi\.com)$",
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/ready")
async def ready() -> dict[str, object]:
    return build_production_readiness(status_path=daily_status_path, snapshot_path=snapshot_data_path)


def is_local_request(request: Request) -> bool:
    hostname = request.url.hostname or ""
    return hostname in {"127.0.0.1", "localhost", "testserver"}


def can_run_live_prediction(request: Request, x_admin_token: str | None) -> bool:
    expected = resolve_admin_token(request)
    if expected:
        return bool(x_admin_token and compare_digest(x_admin_token, expected))
    return is_local_request(request)


@app.get("/api/match-prediction")
async def match_prediction(
    request: Request,
    simulations: int = Query(SIMULATION_COUNT, ge=1_000, le=50_000),
    use_snapshot: bool = Query(True, alias="useSnapshot"),
    x_admin_token: str | None = Header(default=None),
) -> dict[str, object]:
    snapshot = read_prediction_snapshot(snapshot_data_path)
    if use_snapshot or not can_run_live_prediction(request, x_admin_token):
        if snapshot is not None:
            return snapshot
        raise HTTPException(status_code=503, detail="预测快照暂不可用")
    now = monotonic()
    cached = prediction_cache.get(simulations)
    if cached and now - cached[0] < PREDICTION_CACHE_TTL_SECONDS:
        return cached[1]
    prediction = build_match_prediction(simulations)
    prediction["dailyMovers"] = build_probability_movers(prediction, None)
    prediction_cache[simulations] = (now, prediction)
    return prediction


@app.get("/api/model-status")
async def model_status() -> dict[str, object]:
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
async def access_options() -> dict[str, object]:
    return build_access_options(payment_configured=bool(build_payment_config()["ready"]))


@app.get("/api/access-policy")
async def access_policy() -> dict[str, object]:
    return build_access_policy(payment_configured=bool(build_payment_config()["ready"]))


@app.get("/api/access-decision")
async def access_decision(orderId: str, contentKey: str, matchKey: str | None = None) -> dict[str, object]:
    return build_order_access_decision(orderId, contentKey, matchKey, payment_orders_path)


@app.get("/api/payments/config")
async def payment_config() -> dict[str, object]:
    return build_payment_config()


@app.post("/api/payments/orders")
async def create_order(request: PaymentOrderCreateRequest) -> dict[str, object]:
    try:
        metadata = {
            "contentKey": request.contentKey,
            "matchKey": request.matchKey,
            "homeTeam": request.homeTeam,
            "awayTeam": request.awayTeam,
            "homeName": request.homeName,
            "awayName": request.awayName,
            "wechatOpenId": request.wechatOpenId,
        }
        return create_payment_order(request.productKey, request.provider, metadata=metadata, storage_path=payment_orders_path)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.get("/api/payments/orders/{order_id}")
async def payment_order(order_id: str, sync: bool = Query(False)) -> dict[str, object]:
    try:
        if sync:
            return refresh_payment_order_status(order_id, storage_path=payment_orders_path)
        return get_payment_order(order_id, payment_orders_path)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="支付订单不存在") from error


@app.post("/api/payments/notify/{provider}")
async def payment_notify(provider: str, request: Request) -> dict[str, object]:
    result = handle_payment_notification(provider, await request.body(), request.headers, storage_path=payment_orders_path)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=str(result.get("reason") or "payment_notify_failed"))
    return result


@app.post("/api/app-payment/wechat/notify")
async def wechat_native_payment_notify(request: Request) -> dict[str, object]:
    result = handle_payment_notification("wechat_native", await request.body(), request.headers, storage_path=payment_orders_path)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=str(result.get("reason") or "payment_notify_failed"))
    return result


@app.get("/api/admin/overview")
async def admin_overview(_: None = Depends(verify_admin_token)) -> dict[str, object]:
    return build_admin_overview(snapshot_data_path, audit_log_path, daily_status_path, tournament_backup_dir)


@app.get("/api/admin/prediction-run")
async def admin_prediction_run(_: None = Depends(verify_admin_token)) -> dict[str, object]:
    return build_prediction_run_monitor(snapshot_data_path, daily_status_path)


@app.get("/api/upcoming-matches")
async def upcoming_matches(limit: int = Query(12, ge=1, le=72)) -> dict[str, object]:
    return build_upcoming_match_predictions(limit)


@app.get("/api/public-upcoming-matches")
async def public_upcoming_matches(limit: int = Query(12, ge=1, le=72)) -> dict[str, object]:
    return build_public_upcoming_match_list(limit)


@app.get("/api/public-match-summary")
async def public_match_summary(home: str, away: str) -> dict[str, object]:
    try:
        return build_public_match_summary(home, away)
    except FinishedMatchPredictionError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.get("/api/finished-matches")
async def finished_matches(limit: int = Query(12, ge=1, le=72)) -> dict[str, object]:
    return build_finished_match_records(limit)


@app.get("/api/public-finished-matches")
async def public_finished_matches(limit: int = Query(12, ge=1, le=72)) -> dict[str, object]:
    return build_public_finished_match_records(limit)


@app.get("/api/finished-match-review")
async def finished_match_review(home: str, away: str, orderId: str) -> dict[str, object]:
    decision = build_order_access_decision(orderId, "post_match_review", storage_path=payment_orders_path)
    if not decision["allowed"]:
        raise HTTPException(status_code=403, detail="赛后复盘尚未解锁")
    try:
        order = get_payment_order(orderId, payment_orders_path)
        metadata = order.get("metadata")
        if order.get("productKey") == "single_match" and isinstance(metadata, dict):
            scoped_home = metadata.get("homeTeam")
            scoped_away = metadata.get("awayTeam")
            if scoped_home and scoped_away and (scoped_home != home or scoped_away != away):
                raise HTTPException(status_code=403, detail="该订单不包含这场赛后复盘")
        return build_finished_match_review(home, away)
    except HTTPException:
        raise
    except KeyError as error:
        raise HTTPException(status_code=404, detail="支付订单不存在") from error
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.get("/api/match-detail")
async def match_detail(
    home: str,
    away: str,
    simulations: int = Query(1200, ge=1_000, le=50_000),
    orderId: str | None = None,
) -> dict[str, object]:
    if os.environ.get("WORLD_CUP_REQUIRE_MATCH_DETAIL_PAYMENT") == "1":
        if not orderId:
            raise HTTPException(status_code=403, detail="需要先完成支付解锁")
        decision = build_order_access_decision(orderId, "match_prediction", match_key=f"{home}-{away}", storage_path=payment_orders_path)
        if not decision.get("allowed"):
            raise HTTPException(status_code=403, detail="订单未解锁该场预测")
    try:
        return build_match_detail(home, away, simulations)
    except FinishedMatchPredictionError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.get("/api/events")
async def events(_: None = Depends(verify_admin_token)) -> dict[str, object]:
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
async def review_event(request: EventReviewRequest, _: None = Depends(verify_admin_token)) -> dict[str, object]:
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
async def create_raw_news(request: RawNewsCreateRequest, _: None = Depends(verify_admin_token)) -> dict[str, object]:
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
async def rebuild_snapshot(request: SnapshotRebuildRequest, _: None = Depends(verify_admin_token)) -> dict[str, object]:
    reload_model_data(review_data_path, fixtures_data_path)
    payload = write_prediction_snapshot(snapshot_data_path, request.simulations)
    append_admin_audit("snapshot:rebuild", str(snapshot_data_path), {"simulations": request.simulations}, audit_log_path)
    prediction_cache.clear()
    return payload


@app.post("/api/fixtures/result")
async def update_fixture_result(request: FixtureResultRequest, _: None = Depends(verify_admin_token)) -> dict[str, object]:
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
async def update_fixture_live_score(request: FixtureResultRequest, _: None = Depends(verify_admin_token)) -> dict[str, object]:
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
async def import_tournament_data(payload: dict[str, object], _: None = Depends(verify_admin_token)) -> dict[str, object]:
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
async def rollback_tournament_data(request: TournamentRollbackRequest, _: None = Depends(verify_admin_token)) -> dict[str, object]:
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


if os.environ.get("WORLD_CUP_SERVE_STATIC") == "1" and STATIC_DIST_DIR.exists():
    assets_dir = STATIC_DIST_DIR / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str) -> FileResponse:
        target = STATIC_DIST_DIR / full_path
        if target.is_file():
            return FileResponse(target)
        return FileResponse(STATIC_DIST_DIR / "index.html")
