from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urldefrag, urljoin, urlsplit, urlunsplit

import requests
import yaml
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from parsers.common import (
    ItemCandidate,
    ParsedOfficialItem,
    candidates_from_dom_links,
    discover_candidates,
    item_content_hash as official_item_content_hash,
    merge_candidates as merge_official_candidates,
    parser_quality,
    stable_item_id,
)
from parsers.spacex_launches import PARSER_VERSION as SPACEX_PARSER_VERSION
from parsers.spacex_launches import parse_official_item as parse_spacex_launch
from parsers.starlink_updates import PARSER_VERSION as STARLINK_PARSER_VERSION
from parsers.starlink_updates import parse_official_item as parse_starlink_update


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCES_FILE = PROJECT_ROOT / "sources.yml"
ITEMS_FILE = PROJECT_ROOT / "data" / "items.jsonl"
SOURCE_STATUS_FILE = PROJECT_ROOT / "data" / "source_status.json"
EXTRACTION_QUALITY_FILE = PROJECT_ROOT / "data" / "extraction_quality.json"
ITEM_EXTRACTION_STATE_FILE = PROJECT_ROOT / "data" / "item_extraction_state.json"
ITEM_EXTRACTION_REPORT_FILE = PROJECT_ROOT / "data" / "item_extraction_report.json"
RAW_DIR = PROJECT_ROOT / "data" / "raw"
USER_AGENT = "starlink-intel-weekly/phase4a (+official-source-monitoring)"
COLLECTOR_NAME = "official_item_extraction_v1"
PARSER_VERSION = COLLECTOR_NAME
SUPPORTED_SOURCE_IDS = {"starlink_official_updates", "spacex_official_launches"}

SOURCE_KEYWORDS = {
    "starlink_official_updates": [
        "starlink",
        "update",
        "updates",
        "satellite",
        "internet",
        "network",
        "service",
        "mini",
        "roam",
        "residential",
        "aviation",
        "maritime",
        "direct to cell",
        "terminal",
    ],
    "spacex_official_launches": [
        "launch",
        "launches",
        "mission",
        "missions",
        "starlink",
        "falcon",
        "dragon",
        "crew",
        "rideshare",
        "payload",
        "orbit",
    ],
}

OFFICIAL_HOST_SUFFIX = {
    "starlink_official_updates": "starlink.com",
    "spacex_official_launches": "spacex.com",
}

EXCLUDED_PATH_PARTS = {
    "account",
    "auth",
    "careers",
    "checkout",
    "contact",
    "cookies",
    "legal",
    "login",
    "merch",
    "order",
    "privacy",
    "shop",
    "signin",
    "signup",
    "support",
    "terms",
}

QUALITY_RANK = {"high": 3, "medium": 2, "low": 1, "unknown": 0}
LEVEL_RANK = {"item_level": 3, "link_level": 2, "page_level": 1, "unknown": 0}


@dataclass
class SourceFetch:
    source: dict[str, Any]
    fetched_at: str
    http_status: int | None
    reachable: bool
    html: str = ""
    page_hash: str | None = None
    page_text: str = ""
    error: str | None = None


@dataclass
class CollectResult:
    items: list[dict[str, Any]]
    sources: list[str]
    errors: list[str]
    source_statuses: dict[str, dict[str, Any]] = field(default_factory=dict)
    extraction_quality: dict[str, Any] = field(default_factory=dict)
    item_extraction_state: dict[str, Any] = field(default_factory=dict)
    item_extraction_report: dict[str, Any] = field(default_factory=dict)
    baseline_count: int = 0
    new_count: int = 0
    changed_count: int = 0
    unchanged_count: int = 0
    total_items: int = 0
    wrote_items: bool = False
    wrote_status: bool = False
    wrote_quality: bool = False
    wrote_item_state: bool = False
    wrote_item_report: bool = False

    @property
    def page_change_status(self) -> str:
        if not self.source_statuses:
            return "unknown"
        statuses = sorted({str(status.get("change_status", "unknown")) for status in self.source_statuses.values()})
        return ",".join(statuses)

    @property
    def health_status(self) -> str:
        if not self.source_statuses:
            return "unknown"
        statuses = sorted({str(status.get("health_status", "unknown")) for status in self.source_statuses.values()})
        return ",".join(statuses)


@dataclass
class OfficialExtractionOutcome:
    items: list[dict[str, Any]] = field(default_factory=list)
    candidates: list[ItemCandidate] = field(default_factory=list)
    static_candidate_count: int = 0
    rendered_candidate_count: int = 0
    detail_fetch_success: int = 0
    detail_fetch_failed: int = 0
    page_level_fallback: bool = False
    render_fallback_used: bool = False
    render_fallback_status: str = "not_needed"
    parser_version: str = "unknown"
    extraction_succeeded: bool = False
    warnings: list[str] = field(default_factory=list)

def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def normalize_text(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", value).strip()


def compute_hash(value: str | None) -> str:
    normalized = normalize_text(value)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def load_sources(path: Path = SOURCES_FILE) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"来源配置文件不存在：{path}")

    with path.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}

    sources = data.get("sources", [])
    if not isinstance(sources, list):
        raise ValueError("sources.yml 格式错误：sources 必须是列表。")
    return sources


def load_items(path: Path = ITEMS_FILE) -> list[dict[str, Any]]:
    if not path.exists():
        return []

    items: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                item = json.loads(stripped)
            except json.JSONDecodeError:
                print(f"跳过无法解析的 JSONL 行：{path}:{line_number}")
                continue
            if isinstance(item, dict):
                items.append(item)
    return items


def load_source_status(path: Path = SOURCE_STATUS_FILE) -> dict[str, Any]:
    if not path.exists():
        return {"generated_at": None, "sources": {}}

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        print(f"来源状态文件无法解析，将重新生成：{path}")
        return {"generated_at": None, "sources": {}}

    if not isinstance(data, dict):
        return {"generated_at": None, "sources": {}}
    if not isinstance(data.get("sources"), dict):
        data["sources"] = {}
    return data


def write_source_status(status: dict[str, Any], path: Path = SOURCE_STATUS_FILE) -> None:
    status["generated_at"] = now_iso()
    write_json_atomic(path, status)


def load_extraction_quality(path: Path = EXTRACTION_QUALITY_FILE) -> dict[str, Any]:
    if not path.exists():
        return {"generated_at": None, "parser_version": PARSER_VERSION, "sources": {}}

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        print(f"解析质量文件无法解析，将重新生成：{path}")
        return {"generated_at": None, "parser_version": PARSER_VERSION, "sources": {}}

    if not isinstance(data, dict):
        return {"generated_at": None, "parser_version": PARSER_VERSION, "sources": {}}
    if not isinstance(data.get("sources"), dict):
        data["sources"] = {}
    data["parser_version"] = PARSER_VERSION
    return data


def write_extraction_quality(quality: dict[str, Any], path: Path = EXTRACTION_QUALITY_FILE) -> None:
    quality["generated_at"] = now_iso()
    quality["parser_version"] = PARSER_VERSION
    write_json_atomic(path, quality)


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(temporary, path)


def load_item_extraction_state(path: Path = ITEM_EXTRACTION_STATE_FILE) -> dict[str, Any]:
    default = {"version": 1, "generated_at": None, "sources": {}}
    if not path.exists():
        return default
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        print(f"条目抽取状态文件无法解析，将使用未完成 baseline 的内存状态：{path}")
        return default
    if not isinstance(payload, dict):
        return default
    if not isinstance(payload.get("sources"), dict):
        payload["sources"] = {}
    payload["version"] = 1
    return payload


def load_item_extraction_report(path: Path = ITEM_EXTRACTION_REPORT_FILE) -> dict[str, Any]:
    default = {"version": 1, "generated_at": None, "sources": {}}
    if not path.exists():
        return default
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default
    if not isinstance(payload, dict):
        return default
    if not isinstance(payload.get("sources"), dict):
        payload["sources"] = {}
    return payload


def write_item_extraction_state(state: dict[str, Any], path: Path = ITEM_EXTRACTION_STATE_FILE) -> None:
    state["version"] = 1
    state["generated_at"] = now_iso()
    write_json_atomic(path, state)


def write_item_extraction_report(report: dict[str, Any], path: Path = ITEM_EXTRACTION_REPORT_FILE) -> None:
    report["version"] = 1
    report["stage"] = "4A"
    report["generated_at"] = now_iso()
    write_json_atomic(path, report)


def make_item_id(url: str, title: str) -> str:
    return compute_hash(f"{url}|{title}")


def item_content_hash(item: dict[str, Any]) -> str:
    return compute_hash(
        " ".join(
            [
                str(item.get("title") or ""),
                str(item.get("url") or ""),
                str(item.get("summary") or ""),
                str(item.get("evidence") or ""),
            ]
        )
    )


def normalize_url(href: str, base_url: str) -> str | None:
    if not href:
        return None

    absolute = urljoin(base_url, href.strip())
    absolute, _fragment = urldefrag(absolute)
    parts = urlsplit(absolute)
    if parts.scheme not in {"http", "https"}:
        return None
    return urlunsplit((parts.scheme, parts.netloc.lower(), parts.path.rstrip("/") or "/", "", ""))


def source_keywords(source: dict[str, Any]) -> list[str]:
    return SOURCE_KEYWORDS.get(str(source.get("id")), [])


def match_keywords(text: str, keywords: list[str]) -> list[str]:
    searchable = normalize_text(text).lower()
    matched = [keyword for keyword in keywords if keyword.lower() in searchable]
    return sorted(set(matched))


def official_host_suffix(source: dict[str, Any]) -> str:
    return OFFICIAL_HOST_SUFFIX.get(str(source.get("id")), "")


def is_official_source_url(source: dict[str, Any], url: str) -> bool:
    suffix = official_host_suffix(source)
    if not suffix:
        return False
    parts = urlsplit(url)
    return parts.scheme in {"http", "https"} and parts.netloc.lower().endswith(suffix)


def is_excluded_url(url: str) -> bool:
    parts = urlsplit(url)
    path_parts = {part.lower() for part in parts.path.split("/") if part}
    return bool(path_parts & EXCLUDED_PATH_PARTS)


def is_source_related_url(source: dict[str, Any], url: str, text: str = "") -> bool:
    if not is_official_source_url(source, url) or is_excluded_url(url):
        return False

    source_id = str(source.get("id"))
    path = urlsplit(url).path.lower()
    searchable = f"{path} {text}".lower()
    if source_id == "starlink_official_updates":
        return "/updates" in path or bool(match_keywords(searchable, source_keywords(source)))
    if source_id == "spacex_official_launches":
        return any(keyword in searchable for keyword in ("launch", "launches", "mission", "missions", "starlink"))
    return False


def nearby_heading(link_node: Any) -> str:
    container = link_node.find_parent(["article", "section", "li", "div"])
    if not container:
        return ""
    heading = container.find(["h1", "h2", "h3", "h4"])
    return normalize_text(heading.get_text(" ")) if heading else ""


def soup_main_text(soup: BeautifulSoup) -> str:
    text_soup = BeautifulSoup(str(soup), "html.parser")
    for unwanted in text_soup(["script", "style", "noscript", "svg"]):
        unwanted.decompose()
    main = text_soup.find("main")
    if main:
        return normalize_text(main.get_text(" "))
    return normalize_text(text_soup.get_text(" "))


def page_excerpt(page_text: str, max_length: int = 500) -> str:
    return normalize_text(page_text)[:max_length].strip()


def page_title(soup: BeautifulSoup, fallback: str) -> str:
    if soup.title and soup.title.string:
        return normalize_text(soup.title.string)
    h1 = soup.find("h1")
    if h1:
        return normalize_text(h1.get_text(" "))
    return fallback


def fetch_source(source: dict[str, Any], timeout: int = 20) -> SourceFetch:
    fetched_at = now_iso()
    try:
        response = requests.get(
            source["url"],
            headers={"User-Agent": USER_AGENT},
            timeout=timeout,
        )
        http_status = response.status_code
        response.raise_for_status()
    except requests.RequestException as exc:
        return SourceFetch(
            source=source,
            fetched_at=fetched_at,
            http_status=getattr(getattr(exc, "response", None), "status_code", None),
            reachable=False,
            error=f"采集失败：{exc.__class__.__name__}",
        )

    soup = BeautifulSoup(response.text, "html.parser")
    text = soup_main_text(soup)
    hash_base = text or normalize_text(response.text)
    return SourceFetch(
        source=source,
        fetched_at=fetched_at,
        http_status=http_status,
        reachable=True,
        html=response.text,
        page_hash=compute_hash(hash_base),
        page_text=text,
    )


def confidence_value(extracted_level: str) -> float:
    if extracted_level == "item_level":
        return 0.82
    if extracted_level == "link_level":
        return 0.62
    return 0.35


def source_quality_for_level(extracted_level: str) -> str:
    if extracted_level == "item_level":
        return "high"
    if extracted_level == "link_level":
        return "medium"
    return "low"


def classify_candidate(source: dict[str, Any], candidate: dict[str, Any]) -> tuple[str, str, float]:
    url = str(candidate.get("url") or "")
    path = urlsplit(url).path.strip("/").lower()
    title = str(candidate.get("title") or "")
    evidence = str(candidate.get("evidence") or "")
    generic_paths = {"", "updates", "launch", "launches"}

    if candidate.get("origin") in {"json_ld", "next_data"} and path not in generic_paths and title and len(evidence) >= 60:
        extracted_level = "item_level"
    else:
        extracted_level = "link_level"

    quality = source_quality_for_level(extracted_level)
    return extracted_level, quality, confidence_value(extracted_level)


def candidate_links_payload(candidates: list[dict[str, Any]], limit: int = 5) -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    for candidate in candidates:
        url = str(candidate.get("url") or "").strip()
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        payload.append(
            {
                "title": str(candidate.get("title") or "")[:160],
                "url": url,
                "matched_keywords": list(candidate.get("matched_keywords") or [])[:10],
            }
        )
        if len(payload) >= limit:
            break
    return payload


def build_item(
    source: dict[str, Any],
    title: str,
    url: str,
    fetched_at: str,
    http_status: int | None,
    summary: str,
    evidence: str,
    tags: list[str],
    extracted_level: str,
    matched_keywords: list[str],
    candidate_links: list[dict[str, Any]],
    extraction_notes: str,
) -> dict[str, Any]:
    source_quality = source_quality_for_level(extracted_level)
    item = {
        "id": make_item_id(url, title),
        "source_id": source["id"],
        "source_name": source["name"],
        "source_type": source.get("source_type"),
        "reliability_tier": source.get("reliability_tier"),
        "category": source.get("category"),
        "language": source.get("language"),
        "title": title,
        "url": url,
        "published_at": None,
        "fetched_at": fetched_at,
        "http_status": http_status,
        "tags": sorted(set(tags)),
        "summary": summary,
        "evidence": evidence,
        "extracted_level": extracted_level,
        "source_quality": source_quality,
        "extraction_confidence": confidence_value(extracted_level),
        "matched_keywords": sorted(set(matched_keywords)),
        "candidate_links": candidate_links[:5],
        "extraction_notes": extraction_notes,
        "parser_version": PARSER_VERSION,
        "collector": COLLECTOR_NAME,
    }
    item["content_hash"] = item_content_hash(item)
    return item


def extract_anchor_candidates(source: dict[str, Any], soup: BeautifulSoup) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    keywords = source_keywords(source)
    for link in soup.find_all("a", href=True):
        normalized = normalize_url(link.get("href", ""), source["url"])
        if not normalized:
            continue

        link_text = normalize_text(link.get_text(" "))
        heading = nearby_heading(link)
        text = normalize_text(f"{link_text} {heading}")
        if not is_source_related_url(source, normalized, text):
            continue

        fallback = str(source.get("name") or source.get("id") or "Official Source")
        title = link_text or heading or fallback
        matched = match_keywords(f"{normalized} {title} {text}", keywords)
        candidates.append(
            {
                "url": normalized,
                "title": title,
                "evidence": text[:500] or title,
                "matched_keywords": matched,
                "origin": "anchor",
            }
        )
    return candidates


def _safe_json_loads(text: str) -> Any | None:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _iter_json_objects(value: Any, depth: int = 0) -> list[dict[str, Any]]:
    if depth > 8:
        return []
    if isinstance(value, dict):
        objects = [value]
        for child in value.values():
            objects.extend(_iter_json_objects(child, depth + 1))
        return objects
    if isinstance(value, list):
        objects: list[dict[str, Any]] = []
        for child in value[:200]:
            objects.extend(_iter_json_objects(child, depth + 1))
        return objects
    return []


def _first_text_field(data: dict[str, Any], names: tuple[str, ...]) -> str:
    for name in names:
        value = data.get(name)
        if isinstance(value, str) and normalize_text(value):
            return normalize_text(value)
        if isinstance(value, dict):
            nested = _first_text_field(value, ("name", "headline", "title", "@id", "url"))
            if nested:
                return nested
    return ""


def _first_url_field(data: dict[str, Any], base_url: str) -> str | None:
    for name in ("url", "@id", "href", "path", "slug", "mainEntityOfPage"):
        value = data.get(name)
        if isinstance(value, str):
            normalized = normalize_url(value, base_url)
            if normalized:
                return normalized
        if isinstance(value, dict):
            nested = _first_url_field(value, base_url)
            if nested:
                return nested
    return None


def candidates_from_json_value(source: dict[str, Any], value: Any, origin: str) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    keywords = source_keywords(source)
    for data in _iter_json_objects(value):
        url = _first_url_field(data, str(source.get("url") or ""))
        title = _first_text_field(data, ("headline", "title", "name"))
        description = _first_text_field(data, ("description", "summary", "abstract"))
        evidence = normalize_text(" ".join(part for part in [title, description] if part))
        if not url or not title:
            continue
        if not is_source_related_url(source, url, evidence):
            continue
        matched = match_keywords(f"{url} {title} {description}", keywords)
        candidates.append(
            {
                "url": url,
                "title": title,
                "evidence": evidence[:500],
                "matched_keywords": matched,
                "origin": origin,
            }
        )
    return candidates


def extract_json_ld_candidates(source: dict[str, Any], soup: BeautifulSoup) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for script in soup.find_all("script", attrs={"type": re.compile("ld\\+json", re.I)}):
        text = script.string or script.get_text()
        if not normalize_text(text):
            continue
        value = _safe_json_loads(text)
        if value is None:
            continue
        candidates.extend(candidates_from_json_value(source, value, "json_ld"))
    return candidates


def extract_next_data_candidates(source: dict[str, Any], soup: BeautifulSoup) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    script = soup.find("script", id="__NEXT_DATA__")
    if not script:
        return candidates
    text = script.string or script.get_text()
    if not normalize_text(text):
        return candidates
    value = _safe_json_loads(text)
    if value is None:
        return candidates
    return candidates_from_json_value(source, value, "next_data")


def merge_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[tuple[str, str], dict[str, Any]] = {}
    for candidate in candidates:
        url = str(candidate.get("url") or "").strip()
        title = normalize_text(str(candidate.get("title") or ""))
        if not url or not title:
            continue
        key = (url, title.lower())
        existing = merged.get(key)
        if not existing:
            candidate["title"] = title[:180]
            candidate["evidence"] = normalize_text(str(candidate.get("evidence") or ""))[:500]
            candidate["matched_keywords"] = sorted(set(candidate.get("matched_keywords") or []))
            merged[key] = candidate
            continue

        existing["matched_keywords"] = sorted(set(existing.get("matched_keywords") or []) | set(candidate.get("matched_keywords") or []))
        if len(str(candidate.get("evidence") or "")) > len(str(existing.get("evidence") or "")):
            existing["evidence"] = normalize_text(str(candidate.get("evidence") or ""))[:500]
        if existing.get("origin") == "anchor" and candidate.get("origin") in {"json_ld", "next_data"}:
            existing["origin"] = candidate.get("origin")
    return sorted(merged.values(), key=lambda item: (str(item.get("url")), str(item.get("title"))))


def extract_source_candidates(fetch: SourceFetch) -> list[dict[str, Any]]:
    soup = BeautifulSoup(fetch.html, "html.parser")
    source = fetch.source
    candidates = []
    candidates.extend(extract_anchor_candidates(source, soup))
    candidates.extend(extract_json_ld_candidates(source, soup))
    candidates.extend(extract_next_data_candidates(source, soup))
    return merge_candidates(candidates)


def base_tags_for_source(source: dict[str, Any], matched_keywords: list[str]) -> list[str]:
    source_id = str(source.get("id"))
    tags = ["official"]
    if source_id == "starlink_official_updates":
        tags.extend(["starlink", "updates"])
    elif source_id == "spacex_official_launches":
        tags.extend(["spacex", "launches"])
    if "starlink" in matched_keywords and "starlink" not in tags:
        tags.append("starlink")
    return tags


def build_page_level_item(fetch: SourceFetch, candidates: list[dict[str, Any]]) -> dict[str, Any]:
    source = fetch.source
    soup = BeautifulSoup(fetch.html, "html.parser")
    fallback_title = str(source.get("name") or source.get("id") or "Official Source")
    title = page_title(soup, fallback=fallback_title)
    excerpt = page_excerpt(fetch.page_text)
    matched = match_keywords(f"{title} {source.get('url')} {excerpt}", source_keywords(source))
    if source.get("id") == "spacex_official_launches":
        summary = "规则化采集生成 SpaceX Official Launches 页面级记录。未编造发射时间、任务状态或载荷数量。"
    else:
        summary = "规则化采集生成 Starlink Official Updates 页面级记录。未编造发布时间或具体技术事实。"
    item = build_item(
        source=source,
        title=title or fallback_title,
        url=str(source["url"]),
        fetched_at=fetch.fetched_at,
        http_status=fetch.http_status,
        summary=summary,
        evidence=excerpt[:500],
        tags=base_tags_for_source(source, matched),
        extracted_level="page_level",
        matched_keywords=matched,
        candidate_links=candidate_links_payload(candidates),
        extraction_notes="页面可达，但当前静态规则未识别到稳定的独立条目；保留页面级记录，不补写发布时间或技术事实。",
    )
    item["id"] = compute_hash(f"{source['id']}|page|{source['url']}")
    item["canonical_url"] = str(source["url"])
    item["record_scope"] = "page"
    item["record_type"] = "official_page_monitor"
    item["seen_in_current_index"] = True
    item["content_hash"] = item_content_hash(item)
    return item


def build_items_from_candidates(fetch: SourceFetch, candidates: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    source = fetch.source
    candidate_links = candidate_links_payload(candidates)
    items_by_id: dict[str, dict[str, Any]] = {}
    source_url = normalize_url(str(source.get("url") or ""), str(source.get("url") or ""))

    for candidate in candidates:
        url = str(candidate.get("url") or "")
        title = str(candidate.get("title") or source.get("name") or "Official Source")
        if source_url and url == source_url:
            continue

        extracted_level, _quality, _confidence = classify_candidate(source, candidate)
        matched = list(candidate.get("matched_keywords") or [])
        if source.get("id") == "spacex_official_launches":
            summary = f"规则化解析发现 SpaceX 官方 Launches 相关候选链接：{title}"
        else:
            summary = f"规则化解析发现 Starlink 官方 Updates 相关候选链接：{title}"

        note = (
            "从官方页面结构化数据中识别到相对完整条目；仍不推断未出现的事实。"
            if extracted_level == "item_level"
            else "提取到官方候选链接，但缺少稳定发布时间字段；按链接级记录保存。"
        )
        item = build_item(
            source=source,
            title=title,
            url=url,
            fetched_at=fetch.fetched_at,
            http_status=fetch.http_status,
            summary=summary,
            evidence=str(candidate.get("evidence") or "")[:500],
            tags=base_tags_for_source(source, matched),
            extracted_level=extracted_level,
            matched_keywords=matched,
            candidate_links=candidate_links,
            extraction_notes=note,
        )
        items_by_id[item["id"]] = item
        if len(items_by_id) >= limit:
            break

    return list(items_by_id.values())


def _requests_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=2,
        connect=2,
        read=2,
        backoff_factor=0.4,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml",
        }
    )
    return session


def render_index_candidates(fetch: SourceFetch, timeout_seconds: int = 30, max_scrolls: int = 5) -> tuple[list[ItemCandidate], str]:
    try:
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from playwright.sync_api import sync_playwright
    except ImportError:
        return [], "browser_unavailable"

    links: list[dict[str, Any]] = []
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(user_agent=USER_AGENT)
            page.route(
                "**/*",
                lambda route: route.abort()
                if route.request.resource_type in {"image", "media", "font"}
                else route.continue_(),
            )
            page.goto(
                str(fetch.source["url"]),
                wait_until="domcontentloaded",
                timeout=timeout_seconds * 1000,
            )
            page.wait_for_timeout(7000)
            for _ in range(max_scrolls):
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                page.wait_for_timeout(700)
            links = page.locator("a[href]").evaluate_all(
                """elements => elements.slice(0, 500).map(anchor => ({
                    href: anchor.href || '',
                    text: (anchor.innerText || anchor.textContent || '').trim().slice(0, 240),
                    heading: ((anchor.closest('article,section,li') || anchor.parentElement)
                        ?.querySelector('h1,h2,h3,h4')?.innerText || '').trim().slice(0, 240),
                    context: ((anchor.closest('article,section,li') || anchor.parentElement)?.innerText || '')
                        .trim().slice(0, 800)
                }))"""
            )
            browser.close()
    except PlaywrightTimeoutError:
        return [], "timeout"
    except Exception as exc:  # Browser startup and DOM errors are a non-blocking fallback.
        return [], f"failed:{exc.__class__.__name__}"
    return candidates_from_dom_links(str(fetch.source["id"]), str(fetch.source["url"]), links), "success"


def fetch_detail_html(session: requests.Session, url: str, timeout: int = 15, max_bytes: int = 2_000_000) -> tuple[str, int | None, str | None]:
    try:
        response = session.get(url, timeout=timeout, stream=True)
        status = response.status_code
        response.raise_for_status()
        content_type = str(response.headers.get("Content-Type") or "").lower()
        if "html" not in content_type:
            return "", status, "detail_not_html"
        chunks: list[bytes] = []
        size = 0
        for chunk in response.iter_content(chunk_size=64 * 1024):
            if not chunk:
                continue
            size += len(chunk)
            if size > max_bytes:
                return "", status, "detail_too_large"
            chunks.append(chunk)
        encoding = response.encoding or "utf-8"
        return b"".join(chunks).decode(encoding, errors="replace"), status, None
    except requests.RequestException as exc:
        status = getattr(getattr(exc, "response", None), "status_code", None)
        return "", status, exc.__class__.__name__


def parsed_item_to_record(
    parsed: ParsedOfficialItem,
    source: dict[str, Any],
    fetched_at: str,
    http_status: int | None,
    discovery_method: str,
) -> dict[str, Any]:
    quality, confidence = parser_quality(parsed)
    record = parsed.to_dict()
    canonical_url = record.pop("canonical_url")
    record.update(
        {
            "id": stable_item_id(parsed.source_id, canonical_url),
            "canonical_url": canonical_url,
            "url": canonical_url,
            "source_name": source.get("name"),
            "source_type": source.get("source_type"),
            "reliability_tier": source.get("reliability_tier"),
            "language": source.get("language"),
            "fetched_at": fetched_at,
            "http_status": http_status,
            "record_scope": "item",
            "date_text": record.get("published_date_text"),
            "discovery_method": discovery_method,
            "extracted_level": "item_level",
            "source_quality": quality,
            "extraction_confidence": confidence,
            "collector": COLLECTOR_NAME,
            "candidate_links": [],
            "matched_keywords": ["starlink"] if parsed.starlink_relevance == "direct" else [],
            "extraction_notes": "条目字段来自官方详情页或明确的官方索引证据；未从 URL slug 推断日期或任务事实。",
            "seen_in_current_index": True,
        }
    )
    record["content_hash"] = official_item_content_hash(record)
    return record


def extract_official_items(
    fetch: SourceFetch,
    max_source_items: int,
    render_mode: str = "auto",
) -> OfficialExtractionOutcome:
    source_id = str(fetch.source.get("id") or "")
    parser_version = STARLINK_PARSER_VERSION if source_id == "starlink_official_updates" else SPACEX_PARSER_VERSION
    outcome = OfficialExtractionOutcome(parser_version=parser_version)
    static_candidates = discover_candidates(fetch.html, source_id, str(fetch.source["url"]))
    outcome.static_candidate_count = len(static_candidates)
    candidates = list(static_candidates)

    should_render = render_mode == "always" or (render_mode == "auto" and not static_candidates)
    if should_render:
        outcome.render_fallback_used = True
        rendered, render_status = render_index_candidates(fetch)
        outcome.rendered_candidate_count = len(rendered)
        outcome.render_fallback_status = render_status
        candidates = merge_official_candidates([*candidates, *rendered])
        if render_status != "success":
            outcome.warnings.append(f"render_fallback_{render_status}")
    elif render_mode == "never":
        outcome.render_fallback_status = "disabled"

    outcome.candidates = candidates[:max_source_items]
    session = _requests_session()
    parser = parse_starlink_update if source_id == "starlink_official_updates" else parse_spacex_launch
    for index, candidate in enumerate(outcome.candidates):
        if index:
            time.sleep(0.2)
        detail_html, status, error = fetch_detail_html(session, candidate.canonical_url)
        if error:
            outcome.detail_fetch_failed += 1
            outcome.warnings.append(f"detail_fetch_{error}")
            continue
        parsed = parser(
            detail_html,
            candidate.canonical_url,
            candidate.index_evidence or candidate.evidence,
            candidate.title,
        )
        if parsed is None:
            outcome.detail_fetch_failed += 1
            outcome.warnings.append("detail_parse_insufficient_evidence")
            continue
        outcome.detail_fetch_success += 1
        outcome.items.append(
            parsed_item_to_record(parsed, fetch.source, fetch.fetched_at, status, candidate.origin)
        )

    outcome.extraction_succeeded = bool(outcome.items)
    if not outcome.items:
        candidate_payload = [
            {"url": candidate.canonical_url, "title": candidate.title, "matched_keywords": []}
            for candidate in outcome.candidates
        ]
        outcome.items = [build_page_level_item(fetch, candidate_payload)]
        outcome.page_level_fallback = True
    return outcome


def extract_items(fetch: SourceFetch, limit: int, render_mode: str = "auto") -> OfficialExtractionOutcome:
    source_id = fetch.source.get("id")
    if source_id not in SUPPORTED_SOURCE_IDS:
        print(f"跳过当前阶段未支持的来源：{source_id}")
        return OfficialExtractionOutcome(warnings=["unsupported_source"])
    return extract_official_items(fetch, limit, render_mode)


def apply_item_change_metadata(
    items: list[dict[str, Any]],
    existing_by_id: dict[str, dict[str, Any]],
) -> tuple[int, int, int]:
    new_count = 0
    changed_count = 0
    unchanged_count = 0

    for item in items:
        item_id = item.get("id")
        existing = existing_by_id.get(item_id)
        fetched_at = str(item.get("fetched_at") or now_iso())
        current_hash = item.get("content_hash") or item_content_hash(item)
        item["content_hash"] = current_hash
        item["last_seen_at"] = fetched_at

        if not existing:
            item["first_seen_at"] = fetched_at
            item["last_changed_at"] = fetched_at
            item["change_status"] = "new"
            item["previous_content_hash"] = None
            new_count += 1
            continue

        previous_hash = existing.get("content_hash")
        item["first_seen_at"] = existing.get("first_seen_at") or existing.get("fetched_at") or fetched_at
        item["previous_content_hash"] = previous_hash
        if previous_hash == current_hash:
            item["last_changed_at"] = existing.get("last_changed_at") or item["first_seen_at"]
            item["change_status"] = "unchanged"
            unchanged_count += 1
        else:
            item["last_changed_at"] = fetched_at
            item["change_status"] = "changed"
            changed_count += 1

    return new_count, changed_count, unchanged_count


def apply_official_item_baseline_metadata(
    items: list[dict[str, Any]],
    existing_by_id: dict[str, dict[str, Any]],
    source_state: dict[str, Any],
    extraction_succeeded: bool,
    rebootstrap: bool = False,
) -> tuple[int, int, int, int]:
    if rebootstrap:
        source_state["bootstrap_completed"] = False
        source_state["bootstrap_completed_at"] = None

    baseline_count = 0
    new_count = 0
    changed_count = 0
    unchanged_count = 0
    bootstrap_completed = bool(source_state.get("bootstrap_completed"))
    state_items = source_state.setdefault("items", {})
    source_state["last_attempt_at"] = now_iso()

    for item in items:
        if item.get("record_scope") != "item":
            continue
        item_id = str(item.get("id") or "")
        fetched_at = str(item.get("fetched_at") or now_iso())
        current_hash = str(item.get("content_hash") or official_item_content_hash(item))
        existing = existing_by_id.get(item_id)
        item["content_hash"] = current_hash
        item["last_seen_at"] = fetched_at
        item["first_seen_at"] = (existing or {}).get("first_seen_at") or fetched_at

        if not bootstrap_completed:
            item["change_status"] = "baseline"
            item["previous_content_hash"] = (existing or {}).get("content_hash")
            item["last_changed_at"] = (existing or {}).get("last_changed_at") or fetched_at
            baseline_count += 1
        elif not existing:
            item["change_status"] = "new"
            item["previous_content_hash"] = None
            item["last_changed_at"] = fetched_at
            new_count += 1
        elif existing.get("content_hash") != current_hash:
            item["change_status"] = "changed"
            item["previous_content_hash"] = existing.get("content_hash")
            item["last_changed_at"] = fetched_at
            changed_count += 1
        else:
            item["change_status"] = "unchanged"
            item["previous_content_hash"] = existing.get("content_hash")
            item["last_changed_at"] = existing.get("last_changed_at") or item["first_seen_at"]
            unchanged_count += 1

        state_items[item_id] = {
            "canonical_url": item.get("canonical_url") or item.get("url"),
            "content_hash": current_hash,
            "first_seen_at": item.get("first_seen_at"),
            "last_seen_at": fetched_at,
        }

    if extraction_succeeded:
        source_state["last_success_at"] = now_iso()
        if not bootstrap_completed:
            source_state["bootstrap_completed"] = True
            source_state["bootstrap_completed_at"] = now_iso()
    else:
        source_state.setdefault("bootstrap_completed", bootstrap_completed)
        source_state["last_failure_at"] = now_iso()
    source_state["known_item_count"] = len(state_items)
    return baseline_count, new_count, changed_count, unchanged_count


def write_items_upsert(
    new_items: list[dict[str, Any]],
    path: Path = ITEMS_FILE,
    processed_source_ids: set[str] | None = None,
) -> tuple[int, int, int, int, int]:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing_items = load_items(path)
    by_id = {item.get("id"): item for item in existing_items if item.get("id")}

    if processed_source_ids:
        for existing in by_id.values():
            if existing.get("record_scope") == "item" and existing.get("source_id") in processed_source_ids:
                existing["seen_in_current_index"] = False

    item_level = [item for item in new_items if item.get("record_scope") == "item"]
    baseline_count = sum(1 for item in item_level if item.get("change_status") == "baseline")
    new_count = sum(1 for item in item_level if item.get("change_status") == "new")
    changed_count = sum(1 for item in item_level if item.get("change_status") == "changed")
    unchanged_count = sum(1 for item in item_level if item.get("change_status") == "unchanged")

    for item in new_items:
        item_id = item.get("id")
        if not item_id:
            continue
        merged = dict(by_id.get(item_id, {}))
        merged.update(item)
        by_id[item_id] = merged

    ordered = sorted(
        by_id.values(),
        key=lambda item: str(item.get("last_seen_at") or item.get("fetched_at") or ""),
        reverse=True,
    )
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as file:
        for item in ordered:
            file.write(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n")
    os.replace(temporary, path)

    return baseline_count, new_count, changed_count, unchanged_count, len(ordered)


def dominant_value(values: list[str], rank: dict[str, int], default: str = "unknown") -> str:
    cleaned = [value for value in values if value]
    if not cleaned:
        return default
    counts = Counter(cleaned)
    return sorted(counts, key=lambda value: (counts[value], rank.get(value, 0), value), reverse=True)[0]


def summarize_quality_fields(items: list[dict[str, Any]]) -> dict[str, Any]:
    levels = [str(item.get("extracted_level") or "unknown") for item in items]
    qualities = [str(item.get("source_quality") or "unknown") for item in items]
    confidences = [float(item.get("extraction_confidence") or 0) for item in items]
    candidate_links_total = sum(len(item.get("candidate_links") or []) for item in items)
    item_records = [item for item in items if item.get("record_scope") == "item"]
    page_records = [item for item in items if item.get("record_scope") == "page"]

    def completeness(field: str) -> float | None:
        if not item_records:
            return None
        return round(sum(bool(item.get(field)) for item in item_records) / len(item_records), 2)

    field_evidence_complete = 0
    for item in item_records:
        evidence = item.get("field_evidence") or {}
        if isinstance(evidence, dict) and evidence.get("title") and evidence.get("evidence"):
            field_evidence_complete += 1

    return {
        "dominant_extracted_level": dominant_value(levels, LEVEL_RANK),
        "dominant_source_quality": dominant_value(qualities, QUALITY_RANK),
        "average_confidence": round(sum(confidences) / len(confidences), 2) if confidences else 0.0,
        "candidate_links_total": candidate_links_total,
        "level_counts": dict(sorted(Counter(levels).items())),
        "quality_counts": dict(sorted(Counter(qualities).items())),
        "item_level_count": len(item_records),
        "page_level_count": len(page_records),
        "title_completeness": completeness("title"),
        "date_completeness": completeness("published_at"),
        "evidence_completeness": completeness("evidence"),
        "field_evidence_completeness": round(field_evidence_complete / len(item_records), 2) if item_records else None,
    }


def build_extraction_quality_summary(status: dict[str, Any], items: list[dict[str, Any]]) -> dict[str, Any]:
    quality = summarize_quality_fields(items)
    notes = []
    for item in items:
        note = str(item.get("extraction_notes") or "").strip()
        if note and note not in notes:
            notes.append(note)

    return {
        "source_id": status.get("source_id"),
        "source_name": status.get("source_name"),
        "url": status.get("url"),
        "last_checked_at": status.get("last_checked_at"),
        "http_status": status.get("http_status"),
        "health_status": status.get("health_status"),
        "change_status": status.get("change_status"),
        "items_collected": status.get("items_collected", len(items)),
        "parser_version": status.get("parser_version") or PARSER_VERSION,
        "dominant_extracted_level": quality["dominant_extracted_level"],
        "dominant_source_quality": quality["dominant_source_quality"],
        "average_confidence": quality["average_confidence"],
        "candidate_links_total": quality["candidate_links_total"],
        "level_counts": quality["level_counts"],
        "quality_counts": quality["quality_counts"],
        "item_level_count": quality["item_level_count"],
        "page_level_count": quality["page_level_count"],
        "title_completeness": quality["title_completeness"],
        "date_completeness": quality["date_completeness"],
        "evidence_completeness": quality["evidence_completeness"],
        "field_evidence_completeness": quality["field_evidence_completeness"],
        "notes": notes[:5],
    }


def update_source_status(
    status: dict[str, Any],
    fetch: SourceFetch,
    items: list[dict[str, Any]],
    baseline_count: int,
    new_count: int,
    changed_count: int,
    unchanged_count: int,
    outcome: OfficialExtractionOutcome | None = None,
    bootstrap_completed: bool | None = None,
) -> dict[str, Any]:
    sources = status.setdefault("sources", {})
    source = fetch.source
    source_id = source["id"]
    previous = sources.get(source_id, {})
    previous_page_hash = previous.get("current_page_hash")
    quality = summarize_quality_fields(items)

    if not fetch.reachable:
        change_status = "failed"
        last_changed_at = previous.get("last_changed_at")
    elif not previous_page_hash:
        change_status = "new"
        last_changed_at = fetch.fetched_at
    elif previous_page_hash != fetch.page_hash:
        change_status = "changed"
        last_changed_at = fetch.fetched_at
    else:
        change_status = "unchanged"
        last_changed_at = previous.get("last_changed_at") or fetch.fetched_at

    source_status = {
        "source_id": source_id,
        "source_name": source.get("name"),
        "url": source.get("url"),
        "category": source.get("category"),
        "source_type": source.get("source_type"),
        "reliability_tier": source.get("reliability_tier"),
        "last_checked_at": fetch.fetched_at,
        "http_status": fetch.http_status,
        "reachable": fetch.reachable,
        "health_status": "reachable" if fetch.reachable else "failed",
        "change_status": change_status,
        "current_page_hash": fetch.page_hash,
        "previous_page_hash": previous_page_hash,
        "last_changed_at": last_changed_at,
        "items_collected": len(items),
        "baseline_items": baseline_count,
        "new_items": new_count,
        "changed_items": changed_count,
        "unchanged_items": unchanged_count,
        "dominant_extracted_level": quality["dominant_extracted_level"],
        "dominant_source_quality": quality["dominant_source_quality"],
        "average_confidence": quality["average_confidence"],
        "candidate_links_total": quality["candidate_links_total"],
        "candidate_count": len(outcome.candidates) if outcome else 0,
        "detail_fetch_success": outcome.detail_fetch_success if outcome else 0,
        "detail_fetch_failed": outcome.detail_fetch_failed if outcome else 0,
        "item_level_items": quality["item_level_count"],
        "page_level_items": quality["page_level_count"],
        "page_level_fallback": outcome.page_level_fallback if outcome else True,
        "render_fallback_used": outcome.render_fallback_used if outcome else False,
        "render_fallback_status": outcome.render_fallback_status if outcome else "unknown",
        "bootstrap_completed": bool(bootstrap_completed),
        "error": fetch.error,
        "collector": COLLECTOR_NAME,
        "parser_version": outcome.parser_version if outcome else PARSER_VERSION,
    }
    sources[source_id] = source_status
    return source_status


def write_failed_source_status(status: dict[str, Any], fetch: SourceFetch) -> dict[str, Any]:
    return update_source_status(status, fetch, [], 0, 0, 0, 0)


def save_raw_html(source_id: str, html: str, fetched_at: str) -> Path:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    safe_time = re.sub(r"[^0-9A-Za-z_-]+", "-", fetched_at)
    path = RAW_DIR / f"{source_id}-{safe_time}.html"
    path.write_text(html, encoding="utf-8", newline="\n")
    return path


def collect_source(
    source: dict[str, Any],
    existing_items: dict[str, dict[str, Any]],
    source_status: dict[str, Any],
    item_extraction_state: dict[str, Any],
    item_extraction_report: dict[str, Any],
    limit: int = 20,
    save_raw: bool = False,
    dry_run: bool = False,
    render_mode: str = "auto",
    rebootstrap: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, Any], str | None]:
    fetch = fetch_source(source)
    if not fetch.reachable:
        states = item_extraction_state.setdefault("sources", {})
        state = states.setdefault(source["id"], {"bootstrap_completed": False, "items": {}})
        state["parser_version"] = STARLINK_PARSER_VERSION if source["id"] == "starlink_official_updates" else SPACEX_PARSER_VERSION
        state["last_attempt_at"] = fetch.fetched_at
        state["last_failure_at"] = fetch.fetched_at
        state["last_candidate_count"] = 0
        state["last_item_count"] = 0
        state["last_error_type"] = "index_fetch_failed"
        item_extraction_report.setdefault("sources", {})[source["id"]] = {
            "source_id": source["id"],
            "source_name": source.get("name"),
            "index_url": source.get("url"),
            "checked_at": fetch.fetched_at,
            "parser_version": STARLINK_PARSER_VERSION if source["id"] == "starlink_official_updates" else SPACEX_PARSER_VERSION,
            "static_candidate_count": 0,
            "rendered_candidate_count": 0,
            "selected_candidate_count": 0,
            "candidate_count": 0,
            "detail_fetch_success": 0,
            "detail_fetch_failed": 0,
            "item_level_items": 0,
            "page_level_items": 0,
            "page_level_fallback": True,
            "render_fallback_used": False,
            "render_fallback_status": "not_run",
            "dominant_extracted_level": "unknown",
            "dominant_source_quality": "unknown",
            "title_completeness": None,
            "date_completeness": None,
            "evidence_completeness": None,
            "field_evidence_completeness": None,
            "bootstrap_completed": bool(state.get("bootstrap_completed")),
            "baseline_items": 0,
            "new_items": 0,
            "changed_items": 0,
            "unchanged_items": 0,
            "warnings": ["index_fetch_failed"],
        }
        status = write_failed_source_status(source_status, fetch)
        message = f"{source.get('name', source.get('id'))} 采集失败：{fetch.error}"
        print(message)
        return [], status, message

    if save_raw and not dry_run:
        raw_path = save_raw_html(source["id"], fetch.html, fetch.fetched_at)
        print(f"已保存原始 HTML 到本地 raw 目录：{raw_path}")
    elif save_raw and dry_run:
        print("[dry-run] 已请求页面，但不会保存原始 HTML。")

    outcome = extract_items(fetch, limit, render_mode)
    items = outcome.items
    item_records = [item for item in items if item.get("record_scope") == "item"]
    page_records = [item for item in items if item.get("record_scope") == "page"]
    if page_records:
        apply_item_change_metadata(page_records, existing_items)

    states = item_extraction_state.setdefault("sources", {})
    state = states.setdefault(
        source["id"],
        {"bootstrap_completed": False, "bootstrap_completed_at": None, "known_item_count": 0, "items": {}},
    )
    state["parser_version"] = outcome.parser_version
    state["last_candidate_count"] = len(outcome.candidates)
    state["last_item_count"] = len(item_records)
    state["last_error_type"] = None if outcome.extraction_succeeded else (
        sorted(set(outcome.warnings))[0] if outcome.warnings else "item_extraction_empty"
    )
    baseline_count, new_count, changed_count, unchanged_count = apply_official_item_baseline_metadata(
        item_records,
        existing_items,
        state,
        extraction_succeeded=outcome.extraction_succeeded,
        rebootstrap=rebootstrap,
    )
    status = update_source_status(
        source_status,
        fetch,
        items,
        baseline_count,
        new_count,
        changed_count,
        unchanged_count,
        outcome=outcome,
        bootstrap_completed=state.get("bootstrap_completed"),
    )
    quality = summarize_quality_fields(items)
    relevance_counts = dict(
        sorted(Counter(str(item.get("starlink_relevance") or "unknown") for item in item_records).items())
    )
    item_extraction_report.setdefault("sources", {})[source["id"]] = {
        "source_id": source["id"],
        "source_name": source.get("name"),
        "index_url": source.get("url"),
        "checked_at": fetch.fetched_at,
        "parser_version": outcome.parser_version,
        "static_candidate_count": outcome.static_candidate_count,
        "rendered_candidate_count": outcome.rendered_candidate_count,
        "selected_candidate_count": len(outcome.candidates),
        "candidate_count": len(outcome.candidates),
        "detail_fetch_success": outcome.detail_fetch_success,
        "detail_fetch_failed": outcome.detail_fetch_failed,
        "item_level_items": len(item_records),
        "page_level_items": len(page_records),
        "page_level_fallback": outcome.page_level_fallback,
        "render_fallback_used": outcome.render_fallback_used,
        "render_fallback_status": outcome.render_fallback_status,
        "dominant_extracted_level": quality["dominant_extracted_level"],
        "dominant_source_quality": quality["dominant_source_quality"],
        "title_completeness": quality["title_completeness"],
        "date_completeness": quality["date_completeness"],
        "evidence_completeness": quality["evidence_completeness"],
        "field_evidence_completeness": quality["field_evidence_completeness"],
        "relevance_counts": relevance_counts,
        "bootstrap_completed": bool(state.get("bootstrap_completed")),
        "baseline_items": baseline_count,
        "new_items": new_count,
        "changed_items": changed_count,
        "unchanged_items": unchanged_count,
        "warnings": sorted(set(outcome.warnings))[:10],
    }
    print_source_summary(status)
    return items, status, None


def print_source_summary(status: dict[str, Any]) -> None:
    print(f"来源：{status.get('source_name')}")
    print(f"HTTP 状态：{status.get('http_status')}")
    print(f"页面状态：{status.get('health_status')}")
    print(f"页面变化状态：{status.get('change_status')}")
    print(f"候选数量：{status.get('candidate_count')}")
    print(f"详情成功/失败：{status.get('detail_fetch_success')}/{status.get('detail_fetch_failed')}")
    print(f"采集条目数：{status.get('items_collected')}")
    print(f"baseline 条目数：{status.get('baseline_items')}")
    print(f"新增条目数：{status.get('new_items')}")
    print(f"变化条目数：{status.get('changed_items')}")
    print(f"未变化条目数：{status.get('unchanged_items')}")
    print(f"主导解析层级：{status.get('dominant_extracted_level')}")
    print(f"主导解析质量：{status.get('dominant_source_quality')}")
    print(f"平均解析置信度：{status.get('average_confidence')}")
    print(f"页面级 fallback：{status.get('page_level_fallback')}")
    print(f"受控渲染状态：{status.get('render_fallback_status')}")


def collect_all_sources(
    source_id: str | None = None,
    limit: int = 20,
    dry_run: bool = False,
    save_raw: bool = False,
    fail_on_error: bool = False,
    render_mode: str = "auto",
    bootstrap_mode: str = "baseline",
    rebootstrap_source: str | None = None,
) -> CollectResult:
    try:
        sources = load_sources()
    except (OSError, ValueError, yaml.YAMLError) as exc:
        message = f"读取来源配置失败：{exc}"
        print(message)
        if fail_on_error:
            raise
        return CollectResult(items=[], sources=[], errors=[message])

    enabled_sources = [source for source in sources if source.get("enabled") is True]
    if source_id:
        enabled_sources = [source for source in enabled_sources if source.get("id") == source_id]

    if not enabled_sources:
        message = f"未找到可采集来源：{source_id or 'enabled sources'}"
        print(message)
        return CollectResult(items=[], sources=[], errors=[message])

    existing_items = {item.get("id"): item for item in load_items() if item.get("id")}
    source_status = load_source_status()
    extraction_quality = load_extraction_quality()
    item_extraction_state = load_item_extraction_state()
    item_extraction_report = load_item_extraction_report()
    quality_sources = extraction_quality.setdefault("sources", {})
    all_items: list[dict[str, Any]] = []
    errors: list[str] = []
    source_names: list[str] = []
    source_statuses: dict[str, dict[str, Any]] = {}

    for source in enabled_sources:
        source_id_value = source.get("id")
        if source_id_value not in SUPPORTED_SOURCE_IDS:
            print(f"跳过当前阶段未支持的来源：{source_id_value}")
            continue
        source_names.append(str(source.get("name", source_id_value)))
        items, status, error = collect_source(
            source,
            existing_items=existing_items,
            source_status=source_status,
            item_extraction_state=item_extraction_state,
            item_extraction_report=item_extraction_report,
            limit=limit,
            save_raw=save_raw,
            dry_run=dry_run,
            render_mode=render_mode,
            rebootstrap=rebootstrap_source == source_id_value,
        )
        source_statuses[source["id"]] = status
        quality_sources[source["id"]] = build_extraction_quality_summary(status, items)
        all_items.extend(items)
        for item in items:
            existing_items[item["id"]] = item
        if error:
            errors.append(error)
            if fail_on_error:
                break

    result = CollectResult(
        items=all_items,
        sources=source_names,
        errors=errors,
        source_statuses=source_statuses,
        extraction_quality=extraction_quality,
        item_extraction_state=item_extraction_state,
        item_extraction_report=item_extraction_report,
    )
    result.baseline_count = sum(
        1 for item in all_items if item.get("record_scope") == "item" and item.get("change_status") == "baseline"
    )
    result.new_count = sum(
        1 for item in all_items if item.get("record_scope") == "item" and item.get("change_status") == "new"
    )
    result.changed_count = sum(
        1 for item in all_items if item.get("record_scope") == "item" and item.get("change_status") == "changed"
    )
    result.unchanged_count = sum(
        1 for item in all_items if item.get("record_scope") == "item" and item.get("change_status") == "unchanged"
    )
    result.total_items = len(existing_items)

    if dry_run:
        print(f"[dry-run] 本次解析 {len(all_items)} 条记录，不写入 {ITEMS_FILE}。")
        print(f"[dry-run] 不写入 {SOURCE_STATUS_FILE}。")
        print(f"[dry-run] 不写入 {EXTRACTION_QUALITY_FILE}。")
        print(f"[dry-run] 不写入 {ITEM_EXTRACTION_STATE_FILE}。")
        print(f"[dry-run] 不写入 {ITEM_EXTRACTION_REPORT_FILE}。")
        return result

    if all_items:
        baseline_count, new_count, changed_count, unchanged_count, total_items = write_items_upsert(
            all_items,
            processed_source_ids=set(source_statuses),
        )
        result.baseline_count = baseline_count
        result.new_count = new_count
        result.changed_count = changed_count
        result.unchanged_count = unchanged_count
        result.total_items = total_items
        result.wrote_items = True
        print(
            f"{ITEMS_FILE} 已更新：baseline {baseline_count} 条，新增 {new_count} 条，"
            f"变化 {changed_count} 条，未变化 {unchanged_count} 条，当前总计 {total_items} 条。"
        )
    else:
        result.total_items = len(load_items())
        print("本次未采集到有效条目，未更新 data/items.jsonl。")

    write_source_status(source_status)
    result.wrote_status = True
    print(f"{SOURCE_STATUS_FILE} 已更新。")

    write_extraction_quality(extraction_quality)
    result.wrote_quality = True
    print(f"{EXTRACTION_QUALITY_FILE} 已更新。")

    write_item_extraction_state(item_extraction_state)
    result.wrote_item_state = True
    print(f"{ITEM_EXTRACTION_STATE_FILE} 已更新。")

    write_item_extraction_report(item_extraction_report)
    result.wrote_item_report = True
    print(f"{ITEM_EXTRACTION_REPORT_FILE} 已更新。")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="采集官方来源页面并写入 JSONL。")
    parser.add_argument("--source-id", help="只采集指定来源。")
    parser.add_argument(
        "--limit",
        "--max-source-items",
        dest="limit",
        type=int,
        default=10,
        help="每个来源最多请求和解析的候选详情数，默认 10。",
    )
    parser.add_argument("--render-mode", choices=["auto", "never", "always"], default="auto")
    parser.add_argument("--bootstrap-mode", choices=["baseline"], default="baseline")
    parser.add_argument("--rebootstrap-source", choices=sorted(SUPPORTED_SOURCE_IDS))
    parser.add_argument(
        "--dry-run",
        "--no-write",
        dest="dry_run",
        action="store_true",
        help="执行采集和解析，但不写入任何 data 文件。",
    )
    parser.add_argument("--save-raw", action="store_true", help="保存原始 HTML 到 data/raw/，该目录不提交。")
    parser.add_argument("--fail-on-error", action="store_true", help="任一来源采集失败时返回非 0。")
    args = parser.parse_args()

    if args.limit < 1:
        print("--limit 必须是大于等于 1 的整数。")
        return 2

    result = collect_all_sources(
        source_id=args.source_id,
        limit=args.limit,
        dry_run=args.dry_run,
        save_raw=args.save_raw,
        fail_on_error=args.fail_on_error,
        render_mode=args.render_mode,
        bootstrap_mode=args.bootstrap_mode,
        rebootstrap_source=args.rebootstrap_source,
    )

    print(
        f"采集汇总：来源 {len(result.sources)} 个，解析 {len(result.items)} 条，"
        f"baseline {result.baseline_count} 条，新增 {result.new_count} 条，变化 {result.changed_count} 条，"
        f"未变化 {result.unchanged_count} 条，错误 {len(result.errors)} 个。"
    )

    if result.errors and args.fail_on_error:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
