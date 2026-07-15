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


PARSER_VERSION = "starlink_updates_item_v2"
SOURCE_ID = "starlink_official_updates"
GENERIC_TITLES = {"starlink", "starlink updates", "updates"}


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
    parse_method: str = "static",
) -> ParsedOfficialItem | None:
    canonical = normalize_candidate_url(SOURCE_ID, "https://www.starlink.com/updates", canonical_url)
    if not canonical:
        return None
    soup = BeautifulSoup(html or "", "html.parser")
    json_ld = extract_json_ld_objects(soup)
    field_evidence: dict[str, str] = {}
    method_prefix = "rendered" if parse_method == "rendered" else "static"

    title = ""
    title_source = ""
    for data in json_ld:
        title = clean_text(data.get("headline"), 240)
        if title:
            title_source = f"{method_prefix}_json_ld_headline"
            break
    if not title:
        for data in json_ld:
            title = clean_text(data.get("name"), 240)
            if title:
                title_source = f"{method_prefix}_json_ld_name"
                break
    if not title:
        heading = soup.find("h1")
        title = clean_text(heading.get_text(" ") if heading else "", 240)
        title_source = f"{method_prefix}_h1" if title else ""
    if not title:
        title, raw_source = first_meta_content(soup, (("property", "og:title"),))
        title_source = f"{method_prefix}_og_title" if raw_source else ""
    if not title:
        title, raw_source = first_meta_content(soup, (("name", "twitter:title"),))
        title_source = f"{method_prefix}_twitter_title" if raw_source else ""
    if not title and soup.title:
        title = re.sub(r"\s*[|\-]\s*Starlink.*$", "", clean_text(soup.title.get_text(" "), 240), flags=re.I)
        title_source = f"{method_prefix}_document_title" if title else ""
    if title.lower() in GENERIC_TITLES:
        title = ""
        title_source = ""
    if title:
        field_evidence["title"] = title_source

    blocks = page_text_blocks(soup)
    date_text = ""
    date_source = ""
    modified_text = ""
    modified_at = None
    for data in json_ld:
        date_text = clean_text(data.get("datePublished"))
        if date_text:
            date_source = f"{method_prefix}_json_ld_datePublished"
            break
    for data in json_ld:
        modified_text = clean_text(data.get("dateModified"))
        if modified_text:
            modified_at = normalize_published_at(modified_text)
            if modified_at:
                field_evidence["modified_at"] = f"{method_prefix}_json_ld_dateModified"
            break
    if not date_text:
        time_node = soup.find("time", attrs={"datetime": True})
        date_text = clean_text(time_node.get("datetime") if time_node else "")
        date_source = f"{method_prefix}_time" if date_text else ""
    published_at = normalize_published_at(date_text)
    if not date_text:
        explicit_text = " ".join(blocks)
        date_text, published_at = _index_date(explicit_text)
        date_source = f"{method_prefix}_explicit_date" if date_text else ""
    if not date_text:
        date_text, date_source = first_meta_content(
            soup,
            (("property", "article:published_time"), ("name", "date"), ("itemprop", "datePublished")),
        )
        published_at = normalize_published_at(date_text)
        if date_source:
            date_source = f"{method_prefix}_article_published_time"
    if published_at:
        field_evidence["published_at"] = date_source

    summary = ""
    summary_source = ""
    for data in json_ld:
        summary = clean_text(data.get("description"), 500)
        if summary:
            summary_source = f"{method_prefix}_json_ld_description"
            break
    if not summary:
        summary, raw_source = first_meta_content(soup, (("name", "description"),))
        summary_source = f"{method_prefix}_meta_description" if raw_source else ""
    if not summary:
        summary, raw_source = first_meta_content(soup, (("property", "og:description"),))
        summary_source = f"{method_prefix}_og_description" if raw_source else ""
    evidence = next((block for block in blocks if block != title and len(block) >= 80), "")
    evidence_source = ""
    if evidence:
        if soup.find("article"):
            evidence_source = f"{method_prefix}_article"
        elif soup.find("main"):
            evidence_source = f"{method_prefix}_main"
        else:
            evidence_source = f"{method_prefix}_meaningful_paragraph"
    if not evidence and len(summary) >= 80:
        evidence = summary
        evidence_source = summary_source
    if not summary and evidence:
        summary = evidence[:500]
        summary_source = evidence_source
    if summary:
        field_evidence["summary"] = summary_source
    if evidence:
        field_evidence["evidence"] = evidence_source

    warnings: list[str] = []
    if not published_at and date_text:
        warnings.append("发布时间文本无法按严格 ISO/date 规则解析")
    if not title or len(evidence) < 80:
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
        modified_at=modified_at,
        modified_date_text=modified_text or None,
        detail_parse_method=parse_method,
    )
