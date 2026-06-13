from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any
from xml.etree import ElementTree


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


def parse_news_feed(feed_text: str, source: str, team: str | None, status: str = "single_source") -> list[dict[str, Any]]:
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
        rows.append(
            {
                "id": entry_id(source, url, title),
                "title": title,
                "summary": summary,
                "source": source,
                "team": team,
                "status": status,
                "published_at": published_at,
                "url": url,
            }
        )
    return rows


def import_news_feed(path: Path, feed_text: str, source: str, team: str | None = None) -> dict[str, int]:
    existing_rows = json.loads(path.read_text(encoding="utf-8"))
    existing_urls = {row.get("url") for row in existing_rows}
    imported_rows = []
    skipped = 0
    for row in parse_news_feed(feed_text, source, team):
        if row["url"] in existing_urls:
            skipped += 1
            continue
        imported_rows.append(row)
        existing_urls.add(row["url"])

    if imported_rows:
        path.write_text(json.dumps(existing_rows + imported_rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "imported": len(imported_rows),
        "skipped": skipped,
    }
