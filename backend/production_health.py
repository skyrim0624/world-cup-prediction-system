from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from . import data as data_state
from .daily_update import DEFAULT_DAILY_STATUS_PATH, read_daily_update_status
from .snapshot import DEFAULT_SNAPSHOT_PATH, read_prediction_snapshot

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL_QUALITY_REPORT_PATH = PROJECT_ROOT / "reports/model-quality-report.json"


def parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def hours_since(value: str | None, now: datetime) -> float | None:
    parsed = parse_time(value)
    if parsed is None:
        return None
    return max(0.0, (now - parsed).total_seconds() / 3600)


def check_daily_status(status_path: Path, now: datetime, max_age_hours: int) -> dict[str, Any]:
    status = read_daily_update_status(status_path)
    if status is None:
        return {"status": "fail", "message": "没有日更状态文件", "path": str(status_path)}
    if status.get("status") == "failed":
        return {"status": "fail", "message": status.get("error", "最近一次日更失败"), "path": str(status_path)}
    if status.get("status") != "success":
        return {"status": "fail", "message": f"日更状态异常: {status.get('status')}", "path": str(status_path)}
    age = hours_since(status.get("updatedAt"), now)
    if age is None:
        return {"status": "fail", "message": "日更状态缺少 updatedAt", "path": str(status_path)}
    if age > max_age_hours:
        return {"status": "fail", "message": f"日更超过 {max_age_hours} 小时未成功", "ageHours": round(age, 2), "path": str(status_path)}
    return {"status": "pass", "message": "日更状态新鲜", "ageHours": round(age, 2), "path": str(status_path)}


def check_snapshot(snapshot_path: Path, now: datetime, max_age_hours: int) -> dict[str, Any]:
    snapshot = read_prediction_snapshot(snapshot_path)
    if snapshot is None:
        return {"status": "fail", "message": "预测快照缺失或结构无效", "path": str(snapshot_path)}
    snapshot_meta = snapshot.get("snapshotMeta") if isinstance(snapshot.get("snapshotMeta"), dict) else {}
    age = hours_since(snapshot_meta.get("generatedAt") if isinstance(snapshot_meta, dict) else None, now)
    if age is None:
        return {"status": "fail", "message": "预测快照缺少 generatedAt", "path": str(snapshot_path)}
    if age > max_age_hours:
        return {"status": "fail", "message": f"预测快照超过 {max_age_hours} 小时未更新", "ageHours": round(age, 2), "path": str(snapshot_path)}
    model_meta = snapshot.get("modelMeta") if isinstance(snapshot.get("modelMeta"), dict) else {}
    return {
        "status": "pass",
        "message": "预测快照有效",
        "ageHours": round(age, 2),
        "path": str(snapshot_path),
        "simulationCount": model_meta.get("simulationCount"),
        "lockedResults": model_meta.get("lockedResults"),
    }


def check_model_quality(report_path: Path) -> dict[str, Any]:
    if not report_path.exists():
        return {"status": "warn", "message": "模型质量报告尚未生成", "path": str(report_path)}
    report = json.loads(report_path.read_text(encoding="utf-8"))
    score_quality = report.get("scoreModelQuality") if isinstance(report.get("scoreModelQuality"), dict) else {}
    backtest = report.get("scoreModelBacktest") if isinstance(report.get("scoreModelBacktest"), dict) else {}
    if score_quality.get("status") != "pass":
        return {
            "status": "fail",
            "message": "比分模型回测未达生产阈值",
            "path": str(report_path),
            "failures": score_quality.get("failures", []),
        }
    return {
        "status": "pass",
        "message": "比分模型回测达标",
        "path": str(report_path),
        "evaluatedMatches": backtest.get("evaluatedMatches"),
        "brierScore": backtest.get("brierScore"),
        "logLoss": backtest.get("logLoss"),
    }


def check_dataset() -> dict[str, Any]:
    dataset = data_state.DATASET_META
    failures = []
    if dataset.get("teamCount") != 48:
        failures.append("team_count_not_48")
    if dataset.get("placeholderSlots") != 0:
        failures.append("placeholder_slots_present")
    if dataset.get("fixtureCount", 0) < 72:
        failures.append("fixture_count_too_low")
    return {
        "status": "fail" if failures else "pass",
        "message": "核心数据覆盖正常" if not failures else "核心数据覆盖不足",
        "failures": failures,
        "dataset": dataset,
    }


def summarize_status(checks: dict[str, dict[str, Any]]) -> str:
    statuses = {check.get("status") for check in checks.values()}
    if "fail" in statuses:
        return "fail"
    if "warn" in statuses:
        return "degraded"
    return "ok"


def build_production_readiness(
    status_path: Path = DEFAULT_DAILY_STATUS_PATH,
    snapshot_path: Path = DEFAULT_SNAPSHOT_PATH,
    model_quality_path: Path = DEFAULT_MODEL_QUALITY_REPORT_PATH,
    now_iso: str | None = None,
    max_status_age_hours: int = 2,
    max_snapshot_age_hours: int = 2,
) -> dict[str, Any]:
    now = parse_time(now_iso) if now_iso else datetime.now(UTC)
    checks = {
        "dailyStatus": check_daily_status(status_path, now, max_status_age_hours),
        "snapshot": check_snapshot(snapshot_path, now, max_snapshot_age_hours),
        "modelQuality": check_model_quality(model_quality_path),
        "dataset": check_dataset(),
    }
    return {
        "status": summarize_status(checks),
        "checkedAt": now.isoformat().replace("+00:00", "Z"),
        "checks": checks,
        "thresholds": {
            "maxStatusAgeHours": max_status_age_hours,
            "maxSnapshotAgeHours": max_snapshot_age_hours,
        },
    }
