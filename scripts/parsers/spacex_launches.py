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


PARSER_VERSION = "spacex_launches_item_v1"
SOURCE_ID = "spacex_official_launches"
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
) -> ParsedOfficialItem | None:
    canonical = normalize_candidate_url(SOURCE_ID, "https://www.spacex.com/launches", canonical_url)
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
        if title.lower() in {"spacex", "spacex launches"}:
            title = ""
            title_source = ""
    if not title and soup.title:
        title = re.sub(r"\s*[|\-]\s*SpaceX.*$", "", clean_text(soup.title.get_text(" "), 240), flags=re.I)
        if title.lower() in {"spacex", "spacex launches"}:
            title = ""
        title_source = "title" if title else ""
    if not title and clean_text(candidate_title).lower() not in {"read more", "watch", "learn more"}:
        title = clean_text(candidate_title, 240)
        title_source = "official index title"
    if title:
        field_evidence["title"] = title_source

    blocks = page_text_blocks(soup)
    evidence_from_detail = bool(blocks)
    if not blocks and index_evidence:
        blocks = [clean_text(index_evidence, 1200)]
    evidence = next((block for block in blocks if block != title and len(block) >= 40), "")
    if evidence:
        field_evidence["evidence"] = "detail main/article text" if evidence_from_detail else "official index context"

    date_text = ""
    date_source = ""
    for data in json_ld:
        date_text = clean_text(data.get("datePublished") or data.get("startDate"))
        if date_text:
            date_source = "json-ld datePublished/startDate"
            break
    if not date_text:
        time_node = soup.find("time", attrs={"datetime": True})
        date_text = clean_text(time_node.get("datetime") if time_node else "")
        date_source = "time[datetime]" if date_text else ""
    published_at = normalize_published_at(date_text)
    if not date_text:
        date_text, published_at = _explicit_date(" ".join(blocks))
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
    if not evidence_from_detail and summary.lower().startswith("spacex designs, manufactures"):
        summary = ""
        summary_source = ""
    if not summary and evidence:
        summary = evidence[:500]
        summary_source = "first meaningful official paragraph"
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
        record_type="official_launch",
        category="spacex_launch",
        is_starlink_related=related,
        relevance_reason=relevance_reason,
        starlink_relevance=relevance,
        structured_fields=structured,
        extraction_warnings=warnings,
    )
