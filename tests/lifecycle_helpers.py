from __future__ import annotations

from copy import deepcopy

from scripts.item_lifecycle import extraction_content_hash, semantic_content_hash


SOURCE_ID = "starlink_official_updates"


def item(
    record_id: str = "record-1",
    url: str = "https://starlink.com/updates/example",
    *,
    title: str = "Example update",
    summary: str = "Existing official summary.",
    evidence: str = "Existing official evidence.",
) -> dict:
    value = {
        "id": record_id,
        "source_id": SOURCE_ID,
        "source_name": "Starlink Official Updates",
        "canonical_url": url,
        "url": url,
        "record_scope": "item",
        "extracted_level": "item_level",
        "title": title,
        "published_at": None,
        "modified_at": None,
        "summary": summary,
        "evidence": evidence,
        "structured_fields": {},
        "field_evidence": {"title": "h1", "evidence": "paragraph"},
        "parser_version": "parser-v1",
        "source_quality": "medium",
        "extraction_confidence": 0.8,
        "detail_parse_method": "static",
        "detail_fetch_status": "success",
        "current_run_data_reused": False,
        "first_seen_at": "2026-06-01T00:00:00+00:00",
        "last_seen_at": "2026-06-01T00:00:00+00:00",
        "last_detail_attempt_at": "2026-06-01T00:00:00+00:00",
        "last_detail_success_at": "2026-06-01T00:00:00+00:00",
        "seen_in_current_index": True,
        "starlink_relevance": "direct",
        "change_status": "unchanged",
        "extraction_change_status": "unchanged",
    }
    value["semantic_content_hash"] = semantic_content_hash(value)
    value["content_hash"] = value["semantic_content_hash"]
    value["extraction_hash"] = extraction_content_hash(value)
    return value


def page_record() -> dict:
    value = item("page-1", "https://starlink.com/updates")
    value["record_scope"] = "page"
    value["extracted_level"] = "page_level"
    return value


def complete_observation(complete: bool = True) -> dict[str, dict]:
    return {
        SOURCE_ID: {
            "index_observation_complete": complete,
            "reachable": complete,
            "checked_at": "2026-06-01T00:00:00+00:00",
        }
    }


def clone(value):
    return deepcopy(value)
