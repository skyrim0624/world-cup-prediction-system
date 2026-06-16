from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from . import data as data_state
from .admin_audit import read_recent_admin_audit
from .admin_security import admin_auth_required
from .daily_update import read_daily_update_status
from .daily_health import build_daily_update_health
from .data_import import list_tournament_backups
from .model import SIMULATION_COUNT, event_summary, event_to_news_item
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


def build_run_step(
    step_id: str,
    label: str,
    function_name: str,
    status: str,
    detail: str,
    module_name: str = "backend.model",
    interface_path: str | None = None,
) -> dict[str, Any]:
    return {
        "id": step_id,
        "label": label,
        "functionName": function_name,
        "moduleName": module_name,
        "status": status,
        "detail": detail,
        "interfacePath": interface_path,
    }


def current_match_context() -> dict[str, Any]:
    home_key, away_key = data_state.CURRENT_MATCH
    fixture = next(
        (item for item in data_state.FIXTURES if (item.home, item.away) == data_state.CURRENT_MATCH),
        None,
    )
    home = data_state.TEAM_PROFILES.get(home_key)
    away = data_state.TEAM_PROFILES.get(away_key)
    return {
        "homeTeam": home_key,
        "awayTeam": away_key,
        "homeName": home.name if home else home_key,
        "awayName": away.name if away else away_key,
        "homeCode": home.code if home else home_key[:3].upper(),
        "awayCode": away.code if away else away_key[:3].upper(),
        "stage": fixture.stage if fixture else "当前比赛",
        "kickoff": fixture.kickoff if fixture else "待定",
        "status": fixture.status if fixture else "missing",
    }


def build_prediction_pipeline(snapshot: dict[str, Any] | None, daily_status: dict[str, Any] | None) -> list[dict[str, Any]]:
    dataset = data_state.DATASET_META
    events = event_summary()
    snapshot_meta = snapshot.get("snapshotMeta") if snapshot else None
    model_meta = snapshot.get("modelMeta", {}) if snapshot else {}
    simulation_count = model_meta.get("simulationCount") or daily_status_snapshot_count(daily_status) or SIMULATION_COUNT
    raw_news_count = len(data_state.RAW_NEWS_ITEMS)

    return [
        {
            "id": "data",
            "title": "数据输入",
            "status": "ran",
            "steps": [
                build_run_step(
                    "load-teams",
                    "读取球队评分",
                    "load_team_profiles",
                    "ran",
                    f"{dataset.get('teamCount', 0)} 支球队，{dataset.get('placeholderSlots', 0)} 个占位槽",
                    "backend.data",
                ),
                build_run_step(
                    "load-fixtures",
                    "读取赛程和赛果",
                    "load_fixtures",
                    "ran",
                    f"{dataset.get('fixtureCount', 0)} 场赛程，已锁定 {fixture_status_counts()['finished']} 场",
                    "backend.data",
                ),
                build_run_step(
                    "load-news",
                    "读取新闻和事件",
                    "load_raw_news_items",
                    "ran",
                    f"{raw_news_count} 条原始新闻，{events['watched']} 条结构化事件",
                    "backend.data",
                ),
                build_run_step(
                    "infer-events",
                    "新闻转结构化事件",
                    "events_from_raw_news",
                    "ran" if raw_news_count else "skipped",
                    "已按来源等级和文本关键词生成事件" if raw_news_count else "暂无原始新闻需要转换",
                    "backend.data",
                ),
                build_run_step(
                    "team-strength-layers",
                    "8 层球队强度细化",
                    "build_team_strength_profile",
                    "ran",
                    "基础、近期、强队、阵容、攻防、门将和战术层逐项计算；缺授权数据保持中性",
                    "backend.team_strength",
                ),
            ],
        },
        {
            "id": "match",
            "title": "单场预测",
            "status": "ran",
            "steps": [
                build_run_step(
                    "event-adjustments",
                    "事件修正球队强度",
                    "apply_event_adjustments",
                    "ran",
                    f"{events['applied']} 条入模，{events['ignored']} 条忽略，{events['reviewRequired']} 条待审",
                ),
                build_run_step(
                    "professional-gap-coverage",
                    "9 类专业缺口覆盖",
                    "professional_gap_coverage",
                    "ran",
                    "逐项标记真实 xG、球员模型、首发预测、市场校准、回测、概率校准、贝叶斯更新和战术 matchup 是否接入",
                    "backend.team_strength",
                ),
                build_run_step(
                    "fixture-context",
                    "赛程上下文修正",
                    "build_fixture_context",
                    "ran",
                    "把城市、旅程、开球时间和赛程位置转成边际因子",
                ),
                build_run_step(
                    "win-draw-loss",
                    "胜平负概率",
                    "win_draw_loss",
                    "ran",
                    "用攻防强度和 Poisson 进球分布生成 90 分钟概率",
                ),
                build_run_step(
                    "score-distribution",
                    "比分分布",
                    "score_outcomes_for_match",
                    "ran",
                    "输出最可能比分、比分矩阵和进球概率",
                ),
                build_run_step(
                    "market-source",
                    "市场价格源",
                    "build_market_price_delta",
                    "skipped",
                    "未接入授权市场价格源，只保留模型公平概率",
                ),
            ],
        },
        {
            "id": "tournament",
            "title": "整届模拟",
            "status": "ran",
            "steps": [
                build_run_step(
                    "simulate-adjusted",
                    "当前参数模拟",
                    "simulate_tournament",
                    "ran",
                    f"{int(simulation_count):,} 次蒙特卡洛，输出 32 强到冠军概率",
                ),
                build_run_step(
                    "simulate-baseline",
                    "未修正基线模拟",
                    "simulate_tournament",
                    "ran",
                    "作为概率变化的对照基线",
                ),
                build_run_step(
                    "scenario-impact",
                    "单场结果传导",
                    "build_scenario_impacts",
                    "ran",
                    "分别模拟主胜、平局、客胜对路径和冠军概率的影响",
                ),
                build_run_step(
                    "third-place",
                    "小组第三路径",
                    "assign_third_place_slots",
                    "ran",
                    "使用 495 种小组第三组合表分配 32 强席位",
                ),
            ],
        },
        {
            "id": "explanation",
            "title": "解释输出",
            "status": "ran",
            "steps": [
                build_run_step(
                    "factor-impacts",
                    "五大盘面映射",
                    "event_factor_impacts",
                    "ran",
                    "把事件影响聚合到实力、状态、路径、人员、边际盘",
                ),
                build_run_step(
                    "daily-movers",
                    "今日变化榜",
                    "build_probability_movers",
                    "ran" if snapshot and snapshot.get("dailyMovers") else "skipped",
                    "已根据上一快照计算涨跌" if snapshot and snapshot.get("dailyMovers") else "没有上一快照或当前快照，暂不计算涨跌",
                    "backend.snapshot",
                ),
                build_run_step(
                    "snapshot-read",
                    "读取预测快照",
                    "read_prediction_snapshot",
                    "ran" if snapshot_meta else "skipped",
                    f"最近快照 {snapshot_meta.get('generatedAt')}" if snapshot_meta else "暂无快照，接口会实时计算",
                    "backend.snapshot",
                    "/api/match-prediction",
                ),
                build_run_step(
                    "snapshot-write",
                    "写入预测快照",
                    "write_prediction_snapshot",
                    "ran" if snapshot_meta else "manual",
                    "最近一次快照已生成" if snapshot_meta else "需要在后台点击重建快照",
                    "backend.snapshot",
                    "/api/snapshot/rebuild",
                ),
            ],
        },
        {
            "id": "pending",
            "title": "未接入能力",
            "status": "skipped",
            "steps": [
                build_run_step(
                    "official-lineup",
                    "官方首发源",
                    "fetch_official_lineups",
                    "skipped",
                    "赛前一小时首发接口尚未接入",
                    "backend.news_ingest",
                ),
                build_run_step(
                    "live-event-data",
                    "实时事件数据",
                    "fetch_live_event_data",
                    "skipped",
                    "第一版不依赖未授权实时事件数据",
                    "backend.score_feed",
                ),
            ],
        },
    ]


def daily_status_snapshot_count(status: dict[str, Any] | None) -> int | None:
    if not status:
        return None
    snapshot = status.get("snapshot")
    if not isinstance(snapshot, dict):
        return None
    simulation_count = snapshot.get("simulationCount")
    return int(simulation_count) if isinstance(simulation_count, (int, float)) else None


def build_prediction_interfaces(snapshot: dict[str, Any] | None) -> list[dict[str, Any]]:
    prediction_status = "snapshot" if snapshot else "live_compute"
    prediction_detail = "优先返回每日快照" if snapshot else "暂无快照时实时计算"
    return [
        {"method": "GET", "path": "/api/match-prediction", "status": prediction_status, "detail": prediction_detail},
        {"method": "GET", "path": "/api/match-detail", "status": "available", "detail": "按指定球队重算单场预测"},
        {"method": "GET", "path": "/api/upcoming-matches", "status": "available", "detail": "输出未开赛比赛入口"},
        {"method": "GET", "path": "/api/model-status", "status": "available", "detail": "输出模型覆盖范围和已知缺口"},
        {"method": "POST", "path": "/api/snapshot/rebuild", "status": "manual", "detail": "人工触发 8,000 到 50,000 次快照重建"},
        {"method": "POST", "path": "/api/events/review", "status": "manual", "detail": "人工确认或忽略新闻事件"},
        {"method": "POST", "path": "/api/fixtures/result", "status": "manual", "detail": "人工锁定完赛比分并触发路径重算"},
    ]


def build_intervention_points() -> list[dict[str, str]]:
    return [
        {
            "label": "锁定完赛比分",
            "endpoint": "/api/fixtures/result",
            "affects": "积分、小组排名、淘汰赛路径和后续冠军概率",
        },
        {
            "label": "写入进行中比分",
            "endpoint": "/api/fixtures/live",
            "affects": "后台状态和后续快照前的人工校准",
        },
        {
            "label": "录入新闻线索",
            "endpoint": "/api/raw-news",
            "affects": "来源评级、事件池和五大盘面修正",
        },
        {
            "label": "审核新闻事件",
            "endpoint": "/api/events/review",
            "affects": "是否进入模型、是否只做备注或忽略",
        },
        {
            "label": "重建预测快照",
            "endpoint": "/api/snapshot/rebuild",
            "affects": "前台展示的冠军榜、单场预测和变化榜",
        },
        {
            "label": "导入或回滚赛事数据",
            "endpoint": "/api/admin/tournament-data/import",
            "affects": "球队、赛程、来源证明和备份恢复",
        },
    ]


def build_prediction_run_monitor(
    snapshot_path: Path,
    daily_status_path: Path | None = None,
) -> dict[str, Any]:
    snapshot = read_prediction_snapshot(snapshot_path)
    daily_update_status = read_daily_update_status(daily_status_path) if daily_status_path else read_daily_update_status()
    pipeline = build_prediction_pipeline(snapshot, daily_update_status)
    steps = [step for stage in pipeline for step in stage["steps"]]
    ran_steps = len([step for step in steps if step["status"] == "ran"])
    skipped_steps = len([step for step in steps if step["status"] == "skipped"])
    manual_steps = len([step for step in steps if step["status"] == "manual"])
    return {
        "generatedAt": datetime.now(UTC).isoformat(),
        "match": current_match_context(),
        "summary": {
            "totalSteps": len(steps),
            "ranSteps": ran_steps,
            "skippedSteps": skipped_steps,
            "manualSteps": manual_steps,
            "interventionPoints": len(build_intervention_points()),
            "snapshotReady": snapshot is not None,
        },
        "pipeline": pipeline,
        "interfaces": build_prediction_interfaces(snapshot),
        "interventionPoints": build_intervention_points(),
    }


def build_admin_overview(
    snapshot_path: Path,
    audit_path: Path | None = None,
    daily_status_path: Path | None = None,
    tournament_backup_root: Path | None = None,
) -> dict[str, Any]:
    snapshot = read_prediction_snapshot(snapshot_path)
    dataset = data_state.DATASET_META
    daily_update_status = read_daily_update_status(daily_status_path) if daily_status_path else read_daily_update_status()
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
        "dailyUpdateStatus": daily_update_status,
        "dailyUpdateHealth": build_daily_update_health(daily_update_status),
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
