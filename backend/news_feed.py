from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from .io_utils import write_json_atomic


def compact_text(value: str | None) -> str:
    return " ".join((value or "").split())


def entry_id(source: str, url: str, title: str) -> str:
    digest = hashlib.sha1((url or title).encode("utf-8")).hexdigest()[:12]
    return f"{source}-{digest}"


def child_text(element: ElementTree.Element, name: str) -> str:
    child = element.find(name)
    if child is None:
        return ""
    return compact_text("".join(child.itertext()))


def infer_news_team(text: str, team_aliases: dict[str, tuple[str, ...]] | None = None) -> str | None:
    if not team_aliases:
        return None
    lowered = text.lower()
    for team_key, aliases in team_aliases.items():
        for alias in aliases:
            if not alias:
                continue
            if alias.lower() in lowered:
                return team_key
    return None


def infer_news_factor(text: str) -> str:
    lowered = text.lower()
    if any(keyword in text for keyword in ("门将", "扑救")) or any(keyword in lowered for keyword in ("goalkeeper", "keeper")):
        return "goalkeeper"
    if any(keyword in text for keyword in ("中卫", "后卫", "防线", "防守")) or any(keyword in lowered for keyword in ("defender", "centre-back", "center-back", "defence", "defense")):
        return "defense"
    if any(keyword in text for keyword in ("高温", "天气", "旅程", "赛程", "恢复")) or any(keyword in lowered for keyword in ("weather", "travel", "recovery")):
        return "path"
    if any(keyword in text for keyword in ("前锋", "边锋", "射手", "进攻")) or any(keyword in lowered for keyword in ("forward", "striker", "winger", "attack")):
        return "attack"
    return "squad"


def classify_news_item(text: str) -> dict[str, Any]:
    lowered = text.lower()
    if any(keyword in text for keyword in ("停赛", "累计黄牌", "红牌")) or any(keyword in lowered for keyword in ("suspended", "suspension", "red card", "yellow card")):
        return {"category": "suspension", "factor": infer_news_factor(text), "direction": -1, "confidence": 0.9}
    if any(keyword in text for keyword in ("伤情", "受伤", "缺席", "单独恢复", "单独训练")) or any(keyword in lowered for keyword in ("injury", "injured", "misses", "doubt")):
        return {"category": "injury", "factor": infer_news_factor(text), "direction": -1, "confidence": 0.78}
    if any(keyword in text for keyword in ("恢复合练", "复出", "确认可用", "回归")) or any(keyword in lowered for keyword in ("returns", "available", "back in training")):
        return {"category": "availability", "factor": infer_news_factor(text), "direction": 1, "confidence": 0.76}
    if any(keyword in text for keyword in ("首发", "阵容")) or any(keyword in lowered for keyword in ("lineup", "starting xi", "starts")):
        return {"category": "lineup", "factor": "squad", "direction": 0, "confidence": 0.72}
    if any(keyword in text for keyword in ("高温", "天气", "暴雨", "湿度")) or any(keyword in lowered for keyword in ("weather", "heat", "humidity", "rain")):
        return {"category": "weather", "factor": "path", "direction": -1, "confidence": 0.66}
    if any(keyword in text for keyword in ("发布会", "训练")) or any(keyword in lowered for keyword in ("press conference", "training")):
        return {"category": "training", "factor": infer_news_factor(text), "direction": 0, "confidence": 0.58}
    return {"category": "general", "factor": infer_news_factor(text), "direction": 0, "confidence": 0.4}


def parse_news_feed(
    feed_text: str,
    source: str,
    team: str | None,
    status: str = "single_source",
    team_aliases: dict[str, tuple[str, ...]] | None = None,
) -> list[dict[str, Any]]:
    root = ElementTree.fromstring(feed_text)
    items = root.findall("./channel/item")
    if not items:
        items = root.findall("{http://www.w3.org/2005/Atom}entry")

    rows: list[dict[str, Any]] = []
    for item in items:
        title = child_text(item, "title") or child_text(item, "{http://www.w3.org/2005/Atom}title")
        summary = (
            child_text(item, "description")
            or child_text(item, "summary")
            or child_text(item, "{http://www.w3.org/2005/Atom}summary")
        )
        url = child_text(item, "link")
        if not url:
            link = item.find("{http://www.w3.org/2005/Atom}link")
            url = compact_text(link.get("href") if link is not None else "")
        published_at = (
            child_text(item, "pubDate")
            or child_text(item, "published")
            or child_text(item, "updated")
            or child_text(item, "{http://www.w3.org/2005/Atom}published")
            or child_text(item, "{http://www.w3.org/2005/Atom}updated")
            or "待确认"
        )
        if not title:
            continue
        text = f"{title} {summary}"
        classification = classify_news_item(text)
        rows.append(
            {
                "id": entry_id(source, url, title),
                "title": title,
                "summary": summary,
                "source": source,
                "team": team or infer_news_team(text, team_aliases),
                "status": status,
                "published_at": published_at,
                "url": url,
                **classification,
            }
        )
    return rows


def import_news_feed(
    path: Path,
    feed_text: str,
    source: str,
    team: str | None = None,
    known_sources: set[str] | None = None,
    team_aliases: dict[str, tuple[str, ...]] | None = None,
) -> dict[str, int]:
    if known_sources is not None and source not in known_sources:
        raise ValueError(f"未知新闻来源: {source}")
    existing_rows = json.loads(path.read_text(encoding="utf-8"))
    existing_urls = {row.get("url") for row in existing_rows}
    imported_rows = []
    skipped = 0
    for row in parse_news_feed(feed_text, source, team, team_aliases=team_aliases):
        if row["url"] in existing_urls:
            skipped += 1
            continue
        imported_rows.append(row)
        existing_urls.add(row["url"])

    if imported_rows:
        write_json_atomic(path, existing_rows + imported_rows)
    return {
        "imported": len(imported_rows),
        "skipped": skipped,
    }
