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


PARSER_VERSION = "spacex_launches_item_v2"
SOURCE_ID = "spacex_official_launches"
GENERIC_TITLES = {"spacex", "spacex launches", "launches"}
INCIDENTAL_PATTERNS = (
    "previously launched",
    "previously supported",
    "flight of this first stage booster",
    "missions including",
)


def classify_starlink_relevance(title: str, blocks: list[str]) -> tuple[str, bool | None, str]:
    title_text = clean_text(title).lower()
    leading = " ".join(blocks[:3]).lower()
    current_context = f"{title_text} {leading}"
    if re.search(r"\bstarlink\b", title_text):
        return "direct", True, "官方任务标题明确包含 Starlink。"
    all_text = " ".join(blocks).lower()
    starlink_blocks = [block.lower() for block in blocks if "starlink" in block.lower()]
    if starlink_blocks and all(any(pattern in block for pattern in INCIDENTAL_PATTERNS) for block in starlink_blocks):
        return "incidental", False, "Starlink 仅出现在助推器历史等附带上下文中。"
    if re.search(
        r"\bstarlink mission\b|(?:launch(?:ed|ing)?|payload).{0,80}\bstarlink satellites\b|\bstarlink satellites\b",
        current_context,
    ):
        return "direct", True, "官方任务主句明确将当前任务与 Starlink 关联。"
    if "starlink" in all_text and any(pattern in all_text for pattern in INCIDENTAL_PATTERNS):
        return "incidental", False, "Starlink 仅出现在助推器历史等附带上下文中。"
    if title and blocks and "starlink" not in current_context:
        return "not_direct", False, "当前任务标题和主句未明确指向 Starlink。"
    return "unknown", None, "官方页面证据不足，无法判断当前任务是否与 Starlink 直接相关。"


def _explicit_sentence(blocks: list[str], phrase: str, excluded: tuple[str, ...] = ()) -> str:
    for block in blocks:
        for sentence in re.split(r"(?<=[.!?])\s+", block):
            lowered = sentence.lower()
            if phrase in lowered and not any(value in lowered for value in excluded):
                return clean_text(sentence, 600)
    return ""


def _explicit_date(value: str) -> tuple[str, str | None]:
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
    canonical = normalize_candidate_url(SOURCE_ID, "https://www.spacex.com/launches", canonical_url)
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
        title = re.sub(r"\s*[|\-]\s*SpaceX.*$", "", clean_text(soup.title.get_text(" "), 240), flags=re.I)
        title_source = f"{method_prefix}_document_title" if title else ""
    if title.lower() in GENERIC_TITLES:
        title = ""
        title_source = ""
    if title:
        field_evidence["title"] = title_source

    blocks = page_text_blocks(soup)
    evidence_from_detail = bool(blocks)
    evidence = next((block for block in blocks if block != title and len(block) >= 80), "")
    if evidence:
        if soup.find("article"):
            field_evidence["evidence"] = f"{method_prefix}_article"
        elif soup.find("main"):
            field_evidence["evidence"] = f"{method_prefix}_main"
        else:
            field_evidence["evidence"] = f"{method_prefix}_meaningful_paragraph"

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
        date_text, published_at = _explicit_date(" ".join(blocks))
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
    if not evidence_from_detail and summary.lower().startswith("spacex designs, manufactures"):
        summary = ""
        summary_source = ""
    if not summary and evidence:
        summary = evidence[:500]
        summary_source = field_evidence.get("evidence", "")
    if not evidence and len(summary) >= 80:
        evidence = summary
        field_evidence["evidence"] = summary_source
    if summary:
        field_evidence["summary"] = summary_source

    relevance, related, relevance_reason = classify_starlink_relevance(title, blocks)
    targeting_sentence = _explicit_sentence(blocks, "is targeting")
    launched_sentence = _explicit_sentence(blocks, "launched", ("previously launched", "booster"))
    if targeting_sentence:
        mission_status = "targeting"
        mission_status_evidence = targeting_sentence
    elif launched_sentence:
        mission_status = "completed"
        mission_status_evidence = launched_sentence
    else:
        mission_status = "unknown"
        mission_status_evidence = ""

    structured: dict[str, Any] = {
        "mission_status": mission_status,
        "mission_status_evidence": mission_status_evidence or None,
        "vehicle": None,
        "launch_site": None,
        "launch_date_text": date_text or None,
        "payload_text": None,
        "payload_count": None,
        "landing_location": None,
    }
    if mission_status_evidence:
        field_evidence["mission_status"] = mission_status_evidence

    if relevance == "direct":
        payload_match = re.search(r"\b(\d{1,3})\s+Starlink satellites\b", " ".join(blocks), re.I)
        if payload_match:
            structured["payload_count"] = int(payload_match.group(1))
            structured["payload_text"] = payload_match.group(0)
            field_evidence["payload_count"] = payload_match.group(0)

    warnings: list[str] = []
    if not published_at and date_text:
        warnings.append("日期文本无法按严格 ISO/date 规则解析")
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
        record_type="official_launch",
        category="spacex_launch",
        is_starlink_related=related,
        relevance_reason=relevance_reason,
        starlink_relevance=relevance,
        structured_fields=structured,
        extraction_warnings=warnings,
        modified_at=modified_at,
        modified_date_text=modified_text or None,
        detail_parse_method=parse_method,
    )
