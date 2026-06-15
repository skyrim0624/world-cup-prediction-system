from __future__ import annotations

import json
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from .io_utils import write_json_atomic
from .news_feed import classify_news_item, entry_id, infer_news_team, parse_news_feed

REQUEST_HEADERS = {"User-Agent": "world-cup-prediction-system/0.1"}


@dataclass(frozen=True)
class PublicSourceSpec:
    id: str
    kind: str
    source: str
    team: str | None = None
    input_path: Path | None = None
    url: str | None = None
    base_url: str | None = None
    max_items: int | None = None
    items_path: str = "items"
    title_field: str = "title"
    summary_field: str = "summary"
    url_field: str = "url"
    published_field: str = "published_at"


class NewsHtmlParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title_parts: list[str] = []
        self.description = ""
        self.canonical_url = ""
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {key.lower(): value or "" for key, value in attrs}
        if tag.lower() == "title":
            self._in_title = True
            return
        if tag.lower() == "meta":
            name = attributes.get("name", "").lower() or attributes.get("property", "").lower()
            if name in {"description", "og:description"} and attributes.get("content"):
                self.description = attributes["content"].strip()
            if name in {"og:title"} and attributes.get("content") and not self.title_parts:
                self.title_parts.append(attributes["content"].strip())
            return
        if tag.lower() == "link" and attributes.get("rel", "").lower() == "canonical":
            self.canonical_url = attributes.get("href", "").strip()

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title and data.strip():
            self.title_parts.append(data.strip())

    def item(self, source: str, team: str | None, fallback_url: str | None) -> dict[str, Any] | None:
        title = " ".join(" ".join(self.title_parts).split())
        if not title:
            return None
        url = self.canonical_url or fallback_url or ""
        return {
            "id": entry_id(source, url, title),
            "title": title,
            "summary": " ".join(self.description.split()),
            "source": source,
            "team": team,
            "status": "single_source",
            "published_at": "待确认",
            "url": url,
        }


class NewsHtmlIndexParser(HTMLParser):
    def __init__(self, source: str, team: str | None, base_url: str | None, max_items: int | None) -> None:
        super().__init__()
        self.source = source
        self.team = team
        self.base_url = base_url
        self.max_items = max_items
        self.items: list[dict[str, Any]] = []
        self._current_href = ""
        self._current_text_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        attributes = {key.lower(): value or "" for key, value in attrs}
        href = attributes.get("href", "").strip()
        if not href:
            return
        self._current_href = href
        self._current_text_parts = []

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() != "a" or not self._current_href:
            return
        title = " ".join(" ".join(self._current_text_parts).split())
        url = urljoin(self.base_url or "", self._current_href)
        self._current_href = ""
        self._current_text_parts = []
        if not self.should_keep_link(title, url):
            return
        self.items.append(
            {
                "id": entry_id(self.source, url, title),
                "title": title,
                "summary": "",
                "source": self.source,
                "team": self.team,
                "status": "single_source",
                "published_at": "待确认",
                "url": url,
                **classify_news_item(title),
            }
        )

    def handle_data(self, data: str) -> None:
        if self._current_href:
            self._current_text_parts.append(data)

    def should_keep_link(self, title: str, url: str) -> bool:
        if self.max_items is not None and len(self.items) >= self.max_items:
            return False
        if len(title.split()) < 4 and "/news/" not in url:
            return False
        blocked_fragments = ("/about", "/contact", "/tickets", "/store", "/legal", "/privacy")
        return not any(fragment in url.lower() for fragment in blocked_fragments)


def load_public_data_specs(config_path: Path) -> list[PublicSourceSpec]:
    rows = json.loads(config_path.read_text(encoding="utf-8"))
    specs: list[PublicSourceSpec] = []
    for row in rows:
        input_path = Path(row["input"]) if row.get("input") else None
        if input_path is not None and not input_path.is_absolute():
            input_path = config_path.parent / input_path
        specs.append(
            PublicSourceSpec(
                id=row["id"],
                kind=row["kind"],
                source=row["source"],
                team=row.get("team"),
                input_path=input_path,
                url=row.get("url"),
                base_url=row.get("baseUrl"),
                max_items=row.get("maxItems"),
                items_path=row.get("itemsPath", "items"),
                title_field=row.get("titleField", "title"),
                summary_field=row.get("summaryField", "summary"),
                url_field=row.get("urlField", "url"),
                published_field=row.get("publishedField", "published_at"),
            )
        )
    return specs


def load_player_aliases(path: Path) -> dict[str, tuple[str, ...]]:
    if not path.exists():
        return {}
    rows = json.loads(path.read_text(encoding="utf-8"))
    aliases: dict[str, tuple[str, ...]] = {}
    for key, values in rows.items():
        if not isinstance(values, list):
            raise ValueError(f"球员别名必须是数组: {key}")
        aliases[key] = tuple(str(value) for value in values if str(value).strip())
    return aliases


def read_public_source_text(spec: PublicSourceSpec) -> str:
    if spec.input_path is not None:
        return spec.input_path.read_text(encoding="utf-8")
    if spec.url is None:
        raise ValueError(f"公开数据源缺少 input 或 url: {spec.id}")
    with urlopen(Request(spec.url, headers=REQUEST_HEADERS), timeout=20) as response:
        return response.read().decode("utf-8", errors="replace")


def nested_value(payload: Any, path: str) -> Any:
    current = payload
    for part in path.split("."):
        if not part:
            continue
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def parse_html_news(text: str, spec: PublicSourceSpec) -> list[dict[str, Any]]:
    parser = NewsHtmlParser()
    parser.feed(text)
    item = parser.item(spec.source, spec.team, spec.url)
    if item is not None:
        item.update(classify_news_item(f"{item.get('title', '')} {item.get('summary', '')}"))
    return [item] if item is not None else []


def parse_html_index_news(text: str, spec: PublicSourceSpec) -> list[dict[str, Any]]:
    parser = NewsHtmlIndexParser(spec.source, spec.team, spec.base_url or spec.url, spec.max_items)
    parser.feed(text)
    return parser.items


def parse_json_news(text: str, spec: PublicSourceSpec) -> list[dict[str, Any]]:
    payload = json.loads(text)
    items = nested_value(payload, spec.items_path)
    if not isinstance(items, list):
        return []
    rows = []
    for item in items:
        if not isinstance(item, dict):
            continue
        title = str(item.get(spec.title_field) or "").strip()
        if not title:
            continue
        summary = str(item.get(spec.summary_field) or "").strip()
        url = str(item.get(spec.url_field) or "").strip()
        rows.append(
            {
                "id": entry_id(spec.source, url, title),
                "title": title,
                "summary": summary,
                "source": spec.source,
                "team": spec.team,
                "status": "single_source",
                "published_at": str(item.get(spec.published_field) or "待确认"),
                "url": url,
                **classify_news_item(f"{title} {summary}"),
            }
        )
    return rows


def parse_public_source(text: str, spec: PublicSourceSpec) -> list[dict[str, Any]]:
    if spec.kind == "rss":
        rows = parse_news_feed(text, spec.source, spec.team)
    elif spec.kind == "html":
        rows = parse_html_news(text, spec)
    elif spec.kind == "html_index":
        rows = parse_html_index_news(text, spec)
    elif spec.kind == "json_news":
        rows = parse_json_news(text, spec)
    else:
        raise ValueError(f"不支持的公开数据源类型: {spec.kind}")
    return [{**row, "kind": spec.kind, "sourceRegistryId": spec.id} for row in rows]


def infer_news_players(text: str, player_aliases: dict[str, tuple[str, ...]] | None = None) -> list[str]:
    if not player_aliases:
        return []
    lowered = text.lower()
    players = []
    for player_key, aliases in player_aliases.items():
        if any(alias and alias.lower() in lowered for alias in aliases):
            players.append(player_key)
    return sorted(players)


def enrich_public_news_row(
    row: dict[str, Any],
    team_aliases: dict[str, tuple[str, ...]] | None,
    player_aliases: dict[str, tuple[str, ...]] | None,
) -> dict[str, Any]:
    text = f"{row.get('title', '')} {row.get('summary', '')}"
    classification = dict(classify_news_item(text))
    players = infer_news_players(text, player_aliases)
    if players and classification.get("category") in {"injury", "suspension", "availability", "lineup", "training", "general"}:
        classification["category"] = "player_status"
        classification["confidence"] = max(float(classification.get("confidence") or 0), 0.82)
    enriched = {
        **row,
        "team": row.get("team") or infer_news_team(text, team_aliases),
        **classification,
    }
    if players:
        enriched["players"] = players
    return enriched


def verification_signature(row: dict[str, Any]) -> tuple[Any, ...] | None:
    team = row.get("team")
    if not team:
        return None
    return (team, row.get("category"), row.get("factor"), row.get("direction"))


def apply_multi_source_verification(rows: list[dict[str, Any]]) -> None:
    grouped_sources: dict[tuple[Any, ...], set[str]] = {}
    for row in rows:
        signature = verification_signature(row)
        if signature is None:
            continue
        grouped_sources.setdefault(signature, set()).add(str(row.get("source") or ""))
    for row in rows:
        signature = verification_signature(row)
        if signature is None:
            continue
        if len(grouped_sources.get(signature, set())) >= 2 and row.get("status") == "single_source":
            row["status"] = "multi_source"


def route_action(row: dict[str, Any], source_levels: dict[str, str]) -> str:
    source_level = source_levels.get(str(row.get("source") or ""), "C")
    status = row.get("status")
    if status in {"unverified", "rumor"} or source_level == "D":
        return "ignore"
    if source_level == "C" and status not in {"confirmed", "multi_source"}:
        return "watch"
    return "apply"


def dedupe_key(row: dict[str, Any]) -> str:
    url = row.get("url")
    if isinstance(url, str) and url:
        return f"url:{url}"
    return f"id:{row['id']}"


def run_public_data_pipeline(
    raw_news_path: Path,
    specs: list[PublicSourceSpec],
    team_aliases: dict[str, tuple[str, ...]] | None = None,
    player_aliases: dict[str, tuple[str, ...]] | None = None,
    known_sources: set[str] | None = None,
    source_levels: dict[str, str] | None = None,
) -> dict[str, Any]:
    existing_rows = json.loads(raw_news_path.read_text(encoding="utf-8")) if raw_news_path.exists() else []
    existing_keys = {dedupe_key(row) for row in existing_rows}
    source_levels = source_levels or {}
    imported_rows: list[dict[str, Any]] = []
    source_reports = []
    skipped = 0
    failed_sources = 0
    successful_sources = 0

    for spec in specs:
        report_base = {
            "id": spec.id,
            "kind": spec.kind,
            "source": spec.source,
            "url": spec.url,
            "input": str(spec.input_path) if spec.input_path is not None else None,
        }
        try:
            if known_sources is not None and spec.source not in known_sources:
                raise ValueError(f"未知公开数据来源: {spec.source}")
            parsed = parse_public_source(read_public_source_text(spec), spec)
        except Exception as error:  # noqa: BLE001 - 逐源容错，报告具体失败来源，不中断整条日更。
            failed_sources += 1
            source_reports.append(
                {
                    **report_base,
                    "status": "failed",
                    "error": str(error),
                    "parsed": 0,
                    "imported": 0,
                    "skipped": 0,
                }
            )
            continue

        successful_sources += 1
        source_imported = 0
        source_skipped = 0
        for row in parsed:
            enriched = enrich_public_news_row(row, team_aliases, player_aliases)
            key = dedupe_key(enriched)
            if key in existing_keys:
                skipped += 1
                source_skipped += 1
                continue
            imported_rows.append(enriched)
            existing_keys.add(key)
            source_imported += 1
        source_reports.append(
            {
                **report_base,
                "status": "success",
                "parsed": len(parsed),
                "imported": source_imported,
                "skipped": source_skipped,
            }
        )

    merged_rows = existing_rows + imported_rows
    apply_multi_source_verification(merged_rows)
    routing = {"apply": 0, "watch": 0, "ignore": 0}
    for row in imported_rows:
        routing[route_action(row, source_levels)] += 1

    if imported_rows:
        write_json_atomic(raw_news_path, merged_rows)

    multi_source = len([row for row in merged_rows if row.get("status") == "multi_source"])
    status = "success"
    if failed_sources and successful_sources:
        status = "partial_success"
    elif failed_sources and not successful_sources:
        status = "failed"
    return {
        "status": status,
        "sources": source_reports,
        "imported": len(imported_rows),
        "skipped": skipped,
        "failedSources": failed_sources,
        "verification": {
            "singleSource": len([row for row in merged_rows if row.get("status") == "single_source"]),
            "multiSource": multi_source,
        },
        "routing": routing,
    }
