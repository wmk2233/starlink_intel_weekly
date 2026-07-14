from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from bs4 import BeautifulSoup

from .common import (
    ParsedOfficialItem,
    clean_text,
    extract_json_ld_objects,
    first_meta_content,
    normalize_candidate_url,
    normalize_published_at,
    page_text_blocks,
)


PARSER_VERSION = "starlink_updates_item_v1"
SOURCE_ID = "starlink_official_updates"


def _index_date(value: str) -> tuple[str, str | None]:
    match = re.search(
        r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}\b",
        value,
        re.I,
    )
    if not match:
        return "", None
    text = match.group(0)
    try:
        parsed = datetime.strptime(text.title(), "%B %d, %Y").replace(tzinfo=timezone.utc)
    except ValueError:
        return text, None
    return text, parsed.isoformat()


def parse_official_item(
    html: str,
    canonical_url: str,
    index_evidence: str = "",
    candidate_title: str = "",
) -> ParsedOfficialItem | None:
    canonical = normalize_candidate_url(SOURCE_ID, "https://www.starlink.com/updates", canonical_url)
    if not canonical:
        return None
    soup = BeautifulSoup(html or "", "html.parser")
    json_ld = extract_json_ld_objects(soup)
    field_evidence: dict[str, str] = {}

    title = ""
    title_source = ""
    for data in json_ld:
        title = clean_text(data.get("headline") or data.get("name"), 240)
        if title:
            title_source = "json-ld headline/name"
            break
    if not title:
        heading = soup.find("h1")
        title = clean_text(heading.get_text(" ") if heading else "", 240)
        title_source = "h1" if title else ""
    if not title:
        title, title_source = first_meta_content(soup, (("property", "og:title"), ("name", "twitter:title")))
    if not title and soup.title:
        title = re.sub(r"\s*[|\-]\s*Starlink.*$", "", clean_text(soup.title.get_text(" "), 240), flags=re.I)
        title_source = "title" if title else ""
    if not title and clean_text(candidate_title).lower() not in {"read more", "watch", "learn more"}:
        title = clean_text(candidate_title, 240)
        title_source = "official index title"
    if title:
        field_evidence["title"] = title_source

    blocks = page_text_blocks(soup)
    date_text = ""
    date_source = ""
    for data in json_ld:
        date_text = clean_text(data.get("datePublished"))
        if date_text:
            date_source = "json-ld datePublished"
            break
    if not date_text:
        time_node = soup.find("time", attrs={"datetime": True})
        date_text = clean_text(time_node.get("datetime") if time_node else "")
        date_source = "time[datetime]" if date_text else ""
    published_at = normalize_published_at(date_text)
    if not date_text:
        explicit_text = " ".join([*blocks, index_evidence])
        date_text, published_at = _index_date(explicit_text)
        date_source = "explicit official date text" if date_text else ""
    if not date_text:
        date_text, date_source = first_meta_content(
            soup,
            (("property", "article:published_time"), ("name", "date"), ("itemprop", "datePublished")),
        )
        published_at = normalize_published_at(date_text)
    if published_at:
        field_evidence["published_at"] = date_source

    summary = ""
    summary_source = ""
    for data in json_ld:
        summary = clean_text(data.get("description"), 500)
        if summary:
            summary_source = "json-ld description"
            break
    if not summary:
        summary, summary_source = first_meta_content(soup, (("name", "description"),))
    if not summary:
        summary, summary_source = first_meta_content(soup, (("property", "og:description"),))
    evidence = next((block for block in blocks if block != title and len(block) >= 40), "")
    if not evidence:
        evidence = clean_text(index_evidence, 1200)
    if not summary and evidence:
        summary = evidence[:500]
        summary_source = "first meaningful official paragraph"
    if summary:
        field_evidence["summary"] = summary_source
    if evidence:
        field_evidence["evidence"] = "detail main/article text" if blocks else "official index context"

    warnings: list[str] = []
    if not published_at and date_text:
        warnings.append("发布时间文本无法按严格 ISO/date 规则解析")
    if not title or not evidence:
        return None
    return ParsedOfficialItem(
        source_id=SOURCE_ID,
        canonical_url=canonical,
        title=title,
        published_at=published_at,
        published_date_text=date_text or None,
        summary=summary[:500],
        evidence=evidence[:1200],
        field_evidence=field_evidence,
        parser_version=PARSER_VERSION,
        record_type="official_update",
        category="starlink_update",
        is_starlink_related=True,
        relevance_reason="条目来自 Starlink 官方 Updates 详情路径。",
        starlink_relevance="direct",
        extraction_warnings=warnings,
    )
