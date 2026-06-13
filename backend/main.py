from __future__ import annotations

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

from .data import DATASET_META, FIXTURES
from .model import SIMULATION_COUNT, build_match_prediction, event_summary


app = FastAPI(title="World Cup Prediction MVP")

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
def match_prediction(simulations: int = Query(SIMULATION_COUNT, ge=1_000, le=50_000)) -> dict[str, object]:
    return build_match_prediction(simulations)


@app.get("/api/model-status")
def model_status() -> dict[str, object]:
    return {
        "dataset": DATASET_META,
        "simulationCount": SIMULATION_COUNT,
        "lockedResults": len([fixture for fixture in FIXTURES if fixture.status == "finished"]),
        "eventSummary": event_summary(),
        "knownGaps": [
            "官方 48 队名单和真实分组尚未替换当前槽位数据",
            "新闻事件仍为本地结构化样例",
            "暂未接自动抓取和多源交叉验证",
            "暂未接后台录入、支付和权限",
        ],
    }
