from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable
from urllib.parse import urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup

try:
    from llm_summarize import normalize_source_url
except ImportError:  # pragma: no cover - package import in tests
    from scripts.llm_summarize import normalize_source_url


SOURCE_RULES = {
    "starlink_official_updates": ("starlink.com", "/updates/"),
    "spacex_official_launches": ("spacex.com", "/launches/"),
}
CANONICAL_HOSTS = {
    "starlink_official_updates": "starlink.com",
    "spacex_official_launches": "www.spacex.com",
}
MEDIA_SUFFIXES = {
    ".avif", ".css", ".gif", ".ico", ".jpeg", ".jpg", ".js", ".json",
    ".m3u8", ".mov", ".mp3", ".mp4", ".pdf", ".png", ".svg", ".webm", ".webp",
}
JSON_SCRIPT_TYPES = {"application/ld+json", "application/json"}


def clean_text(value: object, limit: int | None = None) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:limit].rstrip() if limit is not None else text


@dataclass
class ItemCandidate:
    source_id: str
    canonical_url: str
    title: str = ""
    evidence: str = ""
    origin: str = "anchor"
    index_evidence: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ParsedOfficialItem:
    source_id: str
    canonical_url: str
    title: str
    published_at: str | None
    published_date_text: str | None
    summary: str
    evidence: str
    field_evidence: dict[str, str]
    parser_version: str
    record_type: str
    category: str
    is_starlink_related: bool | None
    relevance_reason: str
    starlink_relevance: str
    structured_fields: dict[str, Any] = field(default_factory=dict)
    extraction_warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _official_root(hostname: str) -> str:
    hostname = hostname.lower().split(":", 1)[0]
    return hostname[4:] if hostname.startswith("www.") else hostname


def normalize_candidate_url(source_id: str, base_url: str, value: object) -> str | None:
    raw = clean_text(value)
    if not raw or raw.startswith(("mailto:", "tel:", "javascript:", "data:")):
        return None
    candidate = normalize_source_url(urljoin(base_url, raw))
    try:
        parts = urlsplit(candidate)
        base_parts = urlsplit(base_url)
    except ValueError:
        return None
    rule = SOURCE_RULES.get(source_id)
    if not rule or parts.scheme not in {"http", "https"} or not parts.hostname:
        return None
    allowed_root, path_prefix = rule
    if _official_root(parts.hostname) != allowed_root or _official_root(base_parts.hostname or "") != allowed_root:
        return None
    path = parts.path.rstrip("/")
    if not path.lower().startswith(path_prefix) or path.lower() == path_prefix.rstrip("/"):
        return None
    if any(path.lower().endswith(suffix) for suffix in MEDIA_SUFFIXES):
        return None
    canonical_host = CANONICAL_HOSTS[source_id]
    return urlunsplit((parts.scheme, canonical_host, parts.path, parts.query, ""))


def stable_item_id(source_id: str, canonical_url: str) -> str:
    normalized = normalize_source_url(canonical_url)
    return hashlib.sha256(f"{source_id}|{normalized}".encode("utf-8")).hexdigest()[:16]


def item_content_hash(item: dict[str, Any]) -> str:
    fields = {
        "title": item.get("title"),
        "published_at": item.get("published_at"),
        "published_date_text": item.get("published_date_text"),
        "summary": item.get("summary"),
        "evidence": item.get("evidence"),
        "field_evidence": item.get("field_evidence") or {},
        "structured_fields": item.get("structured_fields") or {},
        "starlink_relevance": item.get("starlink_relevance"),
    }
    raw = json.dumps(fields, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _candidate_from_values(
    source_id: str,
    index_url: str,
    url_value: object,
    title: object = "",
    evidence: object = "",
    origin: str = "embedded_json",
) -> ItemCandidate | None:
    canonical = normalize_candidate_url(source_id, index_url, url_value)
    if not canonical:
        return None
    return ItemCandidate(
        source_id=source_id,
        canonical_url=canonical,
        title=clean_text(title, 240),
        evidence=clean_text(evidence, 800),
        origin=origin,
    )


def _iter_json_nodes(value: Any, depth: int = 0) -> Iterable[Any]:
    if depth > 8:
        return
    yield value
    if isinstance(value, dict):
        for child in list(value.values())[:200]:
            yield from _iter_json_nodes(child, depth + 1)
    elif isinstance(value, list):
        for child in value[:200]:
            yield from _iter_json_nodes(child, depth + 1)


def _first_text(data: dict[str, Any], names: tuple[str, ...]) -> str:
    for name in names:
        value = data.get(name)
        if isinstance(value, str) and clean_text(value):
            return clean_text(value)
    return ""


def discover_candidates(html: str, source_id: str, index_url: str) -> list[ItemCandidate]:
    soup = BeautifulSoup(html or "", "html.parser")
    found: list[ItemCandidate] = []

    for anchor in soup.find_all("a", href=True):
        title = clean_text(anchor.get_text(" "), 240)
        container = anchor.find_parent(["article", "section", "li"])
        evidence = clean_text(container.get_text(" ") if container else title, 800)
        candidate = _candidate_from_values(source_id, index_url, anchor.get("href"), title, evidence, "anchor")
        if candidate:
            found.append(candidate)

    for script in soup.find_all("script"):
        script_type = clean_text(script.get("type")).lower()
        script_id = clean_text(script.get("id")).lower()
        if script_type not in JSON_SCRIPT_TYPES and script_id not in {"__next_data__", "__nuxt_data__"}:
            continue
        text = script.string or script.get_text()
        if not text or len(text) > 5_000_000:
            continue
        try:
            payload = json.loads(text)
        except (TypeError, json.JSONDecodeError):
            continue
        origin = "json_ld" if "ld+json" in script_type else "embedded_json"
        for node in _iter_json_nodes(payload):
            if isinstance(node, str):
                candidate = _candidate_from_values(source_id, index_url, node, origin=origin)
                if candidate:
                    found.append(candidate)
                continue
            if not isinstance(node, dict):
                continue
            title = _first_text(node, ("headline", "title", "name"))
            evidence = _first_text(node, ("description", "summary", "abstract"))
            for key in ("url", "@id", "href", "path"):
                candidate = _candidate_from_values(source_id, index_url, node.get(key), title, evidence, origin)
                if candidate:
                    found.append(candidate)

    return merge_candidates(found)


def candidates_from_dom_links(source_id: str, index_url: str, links: list[dict[str, Any]]) -> list[ItemCandidate]:
    found: list[ItemCandidate] = []
    for link in links:
        anchor_text = clean_text(link.get("text"), 240)
        heading = clean_text(link.get("heading"), 240)
        title = heading or ("" if anchor_text.lower() in {"read more", "watch", "learn more"} else anchor_text)
        candidate = _candidate_from_values(
            source_id,
            index_url,
            link.get("href"),
            title,
            link.get("context"),
            "rendered_dom",
        )
        if candidate:
            candidate.index_evidence = clean_text(link.get("context"), 800)
            found.append(candidate)
    return merge_candidates(found)


def merge_candidates(candidates: Iterable[ItemCandidate]) -> list[ItemCandidate]:
    merged: dict[str, ItemCandidate] = {}
    for candidate in candidates:
        existing = merged.get(candidate.canonical_url)
        if not existing:
            merged[candidate.canonical_url] = candidate
            continue
        if not existing.title and candidate.title:
            existing.title = candidate.title
        if len(candidate.evidence) > len(existing.evidence):
            existing.evidence = candidate.evidence
        if len(candidate.index_evidence) > len(existing.index_evidence):
            existing.index_evidence = candidate.index_evidence
        if existing.origin == "anchor" and candidate.origin != "anchor":
            existing.origin = candidate.origin
    return list(merged.values())


def extract_json_ld_objects(soup: BeautifulSoup) -> list[dict[str, Any]]:
    objects: list[dict[str, Any]] = []
    for script in soup.find_all("script", attrs={"type": re.compile(r"ld\+json", re.I)}):
        text = script.string or script.get_text()
        try:
            payload = json.loads(text or "")
        except (TypeError, json.JSONDecodeError):
            continue
        for node in _iter_json_nodes(payload):
            if isinstance(node, dict):
                objects.append(node)
    return objects


def first_meta_content(soup: BeautifulSoup, selectors: Iterable[tuple[str, str]]) -> tuple[str, str]:
    for attribute, value in selectors:
        node = soup.find("meta", attrs={attribute: value})
        content = clean_text(node.get("content") if node else "")
        if content:
            return content, f"meta[{attribute}={value}]"
    return "", ""


def normalize_published_at(value: object) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    candidate = text[:-1] + "+00:00" if text.endswith(("Z", "z")) else text
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        try:
            parsed = datetime.strptime(text, "%Y-%m-%d")
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.isoformat()


def page_text_blocks(soup: BeautifulSoup) -> list[str]:
    cloned = BeautifulSoup(str(soup), "html.parser")
    for node in cloned(["script", "style", "noscript", "svg", "nav", "footer", "form"]):
        node.decompose()
    root = cloned.find("main") or cloned.find("article") or cloned.body or cloned
    blocks: list[str] = []
    seen: set[str] = set()
    for node in root.find_all(["p", "h1", "h2", "h3", "time", "li"]):
        text = clean_text(node.get_text(" "), 1200)
        if len(text) < 20 or text in seen:
            continue
        seen.add(text)
        blocks.append(text)
    return blocks


def parser_quality(item: ParsedOfficialItem) -> tuple[str, float]:
    has_trace = bool(item.canonical_url and item.title and item.evidence and item.source_id)
    if not has_trace:
        return "low", 0.35
    core_evidence = sum(bool(value) for value in item.field_evidence.values())
    if item.published_at and len(item.evidence) >= 80 and core_evidence >= 3 and not item.extraction_warnings:
        return "high", 0.9
    confidence = 0.65 + min(core_evidence, 3) * 0.05 + (0.04 if item.published_at else 0)
    return "medium", round(min(confidence, 0.84), 2)
