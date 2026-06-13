from __future__ import annotations

from time import monotonic

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

from .data import DATASET_META, EVENTS, FIXTURES, RAW_NEWS_ITEMS
from .model import SIMULATION_COUNT, build_match_prediction, event_summary, event_to_news_item
from .snapshot import read_prediction_snapshot


app = FastAPI(title="World Cup Prediction MVP")
PREDICTION_CACHE_TTL_SECONDS = 15
prediction_cache: dict[int, tuple[float, dict[str, object]]] = {}

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://127.0.0.1:5174", "http://localhost:5173", "http://localhost:5174"],
    allow_methods=["GET"],
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
        snapshot = read_prediction_snapshot()
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
        "dataset": DATASET_META,
        "simulationCount": SIMULATION_COUNT,
        "lockedResults": len([fixture for fixture in FIXTURES if fixture.status == "finished"]),
        "eventSummary": event_summary(),
        "knownGaps": [
            "官方 48 队名单和真实分组尚未替换当前槽位数据",
            "新闻抓取仍由本地 raw-news JSON 承接，暂未接外部抓取任务",
            "暂未接后台审核写入和多源交叉验证",
            "暂未接后台录入、支付和权限",
        ],
    }


@app.get("/api/events")
def events() -> dict[str, object]:
    items = []
    for event in EVENTS:
        news_item = event_to_news_item(event)
        items.append(
            {
                **news_item,
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
        "rawNewsCount": len(RAW_NEWS_ITEMS),
        "items": items,
    }
