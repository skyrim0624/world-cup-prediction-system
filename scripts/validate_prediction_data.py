from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.data import (
    CURRENT_MATCH,
    DATA_DIR,
    DATASET_META,
    EVENTS,
    FIXTURES,
    NEWS_SOURCES,
    RAW_NEWS_ITEMS,
    TEAM_PROFILES,
    THIRD_PLACE_COMBINATIONS,
)
from backend.model import advanced_metric_impacts


def main() -> None:
    groups = sorted({team.group for team in TEAM_PROFILES.values()})
    if DATASET_META["teamCount"] != 48:
        raise SystemExit("球队数量必须为 48")
    if DATASET_META.get("placeholderSlots") != 0:
        raise SystemExit("正式数据不能包含占位球队")
    if len(groups) != 12:
        raise SystemExit("小组数量必须为 12")
    for group in groups:
        group_teams = [team for team in TEAM_PROFILES.values() if team.group == group]
        if len(group_teams) != 4:
            raise SystemExit(f"{group} 组必须有 4 支球队")
    if DATASET_META["fixtureCount"] < 72:
        raise SystemExit("小组赛赛程至少需要 72 场")
    if any(fixture.match_no is None for fixture in FIXTURES):
        raise SystemExit("小组赛赛程必须包含 match_no")
    if len(THIRD_PLACE_COMBINATIONS) != 495:
        raise SystemExit("Annex C 第三名组合表必须为 495 种")
    feed_config_path = DATA_DIR / "daily-feed-sources.json"
    if not feed_config_path.exists():
        raise SystemExit("缺少真实新闻 Feed 配置")
    advanced_impacts = advanced_metric_impacts()
    if set(advanced_impacts) != set(TEAM_PROFILES):
        raise SystemExit("高阶指标必须覆盖全部球队")
    if DATASET_META["newsSourceCount"] != len(NEWS_SOURCES):
        raise SystemExit("新闻来源统计不一致")
    if DATASET_META["rawNewsCount"] != len(RAW_NEWS_ITEMS):
        raise SystemExit("原始新闻统计不一致")
    if CURRENT_MATCH[0] not in TEAM_PROFILES or CURRENT_MATCH[1] not in TEAM_PROFILES:
        raise SystemExit("当前比赛包含未知球队")
    for event in EVENTS:
        if event.team is not None and event.team not in TEAM_PROFILES:
            raise SystemExit(f"事件包含未知球队: {event.team}")
    print("数据校验通过")
    print(
        f"球队: {DATASET_META['teamCount']} · 小组: {len(groups)} · 赛程: {DATASET_META['fixtureCount']} · "
        f"事件: {len(EVENTS)} · 原始新闻: {len(RAW_NEWS_ITEMS)}"
    )


if __name__ == "__main__":
    main()
