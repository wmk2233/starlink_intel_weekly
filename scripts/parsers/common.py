from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable
from urllib.parse import urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup

try:
    from llm_summarize import normalize_source_url
except ImportError:  # pragma: no cover - package import in tests
    from scripts.llm_summarize import normalize_source_url

try:
    from item_lifecycle import extraction_content_hash, semantic_content_hash as lifecycle_semantic_content_hash
except ImportError:  # pragma: no cover - package import in tests
    from scripts.item_lifecycle import (
        extraction_content_hash,
        semantic_content_hash as lifecycle_semantic_content_hash,
    )


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
DETAIL_ERROR_TYPES = frozenset(
    {
        "invalid_candidate_url",
        "redirect_outside_allowed_domain",
        "redirect_to_index_page",
        "http_4xx",
        "http_5xx",
        "request_timeout",
        "request_error",
        "invalid_content_type",
        "response_too_large",
        "empty_response",
        "javascript_shell",
        "blocked_or_challenge_page",
        "missing_title",
        "missing_evidence",
        "missing_required_fields",
        "render_unavailable",
        "render_timeout",
        "render_navigation_failed",
        "render_redirect_outside_domain",
        "rendered_missing_title",
        "rendered_missing_evidence",
        "rendered_missing_required_fields",
        "render_limit_reached",
        "parse_error",
        "unknown_error",
    }
)
DETAIL_RENDERABLE_ERRORS = frozenset(
    {
        "empty_response",
        "javascript_shell",
        "missing_title",
        "missing_evidence",
        "missing_required_fields",
    }
)
INDEX_TITLES = {
    "starlink",
    "starlink updates",
    "updates",
    "spacex",
    "spacex launches",
    "launches",
}
BLOCKED_PAGE_MARKERS = (
    "attention required",
    "checking your browser",
    "enable javascript and cookies to continue",
    "verify you are human",
)


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
    modified_at: str | None = None
    modified_date_text: str | None = None
    detail_parse_method: str = "static"

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
    return semantic_content_hash(item)


def _hash_payload(fields: dict[str, Any]) -> str:
    raw = json.dumps(fields, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def semantic_content_hash(item: dict[str, Any]) -> str:
    return lifecycle_semantic_content_hash(item)


def extraction_hash(item: dict[str, Any]) -> str:
    return extraction_content_hash(item)


def detail_page_hash(html: str) -> str | None:
    soup = BeautifulSoup(html or "", "html.parser")
    for node in soup(["script", "style", "noscript", "svg", "nav", "footer", "form"]):
        node.decompose()
    visible = clean_text(soup.get_text(" "))
    return _hash_payload({"visible_text": visible}) if visible else None


def detect_blocked_or_challenge_page(html: str) -> bool:
    text = clean_text(BeautifulSoup(html or "", "html.parser").get_text(" ")).lower()
    return any(marker in text for marker in BLOCKED_PAGE_MARKERS)


def detect_javascript_shell(html: str) -> bool:
    if not clean_text(html):
        return False
    soup = BeautifulSoup(html, "html.parser")
    if detect_blocked_or_challenge_page(html):
        return False
    clone = BeautifulSoup(str(soup), "html.parser")
    for node in clone(["script", "style", "noscript", "svg", "nav", "footer", "form"]):
        node.decompose()
    visible = clean_text(clone.get_text(" "))
    has_content_root = bool(clone.find(["h1", "article", "main"]))
    meaningful_blocks = [block for block in page_text_blocks(soup) if len(block) >= 40]
    javascript_notice = bool(
        re.search(r"javascript\s+(?:is\s+)?(?:required|disabled)|enable\s+javascript", visible, re.I)
    )
    root_only = bool(soup.find(id=re.compile(r"^(?:root|app|__next)$", re.I))) and not meaningful_blocks
    return javascript_notice or root_only or (len(visible) < 80 and not has_content_root and bool(soup.find("script")))


def detail_parse_error(html: str, item: ParsedOfficialItem | None, rendered: bool = False) -> str | None:
    prefix = "rendered_" if rendered else ""
    if not clean_text(html):
        return "rendered_missing_required_fields" if rendered else "empty_response"
    if detect_blocked_or_challenge_page(html):
        return "blocked_or_challenge_page"
    if detect_javascript_shell(html):
        return "rendered_missing_required_fields" if rendered else "javascript_shell"
    if item is not None:
        if not clean_text(item.title):
            return f"{prefix}missing_title"
        if len(clean_text(item.evidence)) < 80:
            return f"{prefix}missing_evidence"
        return None

    soup = BeautifulSoup(html, "html.parser")
    title = clean_text((soup.find("h1") or {}).get_text(" ") if soup.find("h1") else "")
    if not title:
        title, _method = first_meta_content(
            soup,
            (("property", "og:title"), ("name", "twitter:title")),
        )
    if not title or title.lower() in INDEX_TITLES:
        return f"{prefix}missing_title"
    if not any(len(block) >= 80 for block in page_text_blocks(soup)):
        return f"{prefix}missing_evidence"
    return f"{prefix}missing_required_fields"


def _method_rank(method: str) -> int:
    lowered = clean_text(method).lower()
    if "json_ld" in lowered or "json-ld" in lowered or "datepublished" in lowered:
        return 5
    if "h1" in lowered or "time" in lowered or "article" in lowered:
        return 4
    if "main" in lowered:
        return 3
    if "meta" in lowered:
        return 2
    return 1


def merge_static_and_rendered_fields(
    static_item: ParsedOfficialItem | None,
    rendered_item: ParsedOfficialItem | None,
) -> ParsedOfficialItem | None:
    if static_item is None:
        return deepcopy(rendered_item)
    if rendered_item is None:
        return deepcopy(static_item)

    merged = deepcopy(static_item)
    warnings = list(dict.fromkeys([*static_item.extraction_warnings, *rendered_item.extraction_warnings]))
    for field_name in (
        "title",
        "published_at",
        "published_date_text",
        "modified_at",
        "modified_date_text",
        "summary",
        "evidence",
    ):
        static_value = getattr(static_item, field_name)
        rendered_value = getattr(rendered_item, field_name)
        if not static_value and rendered_value:
            setattr(merged, field_name, rendered_value)
            evidence_key = "published_at" if field_name.startswith("published") else (
                "modified_at" if field_name.startswith("modified") else field_name
            )
            if rendered_item.field_evidence.get(evidence_key):
                merged.field_evidence[evidence_key] = rendered_item.field_evidence[evidence_key]
            continue
        if not rendered_value or static_value == rendered_value:
            continue
        evidence_key = "published_at" if field_name.startswith("published") else (
            "modified_at" if field_name.startswith("modified") else field_name
        )
        static_method = static_item.field_evidence.get(evidence_key, "")
        rendered_method = rendered_item.field_evidence.get(evidence_key, "")
        if _method_rank(rendered_method) > _method_rank(static_method):
            setattr(merged, field_name, rendered_value)
            merged.field_evidence[evidence_key] = rendered_method
        warnings.append(f"field_conflict:{evidence_key}")

    for key, value in rendered_item.structured_fields.items():
        if merged.structured_fields.get(key) in (None, "", [], {}) and value not in (None, "", [], {}):
            merged.structured_fields[key] = deepcopy(value)
            if rendered_item.field_evidence.get(key):
                merged.field_evidence[key] = rendered_item.field_evidence[key]
        elif value not in (None, "", [], {}) and merged.structured_fields.get(key) != value:
            warnings.append(f"field_conflict:{key}")

    merged.extraction_warnings = list(dict.fromkeys(warnings))
    merged.detail_parse_method = "static+rendered"
    return merged


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
