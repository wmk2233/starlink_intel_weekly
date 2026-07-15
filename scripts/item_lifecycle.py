from __future__ import annotations

import hashlib
import html
import json
import os
import shutil
import unicodedata
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
ITEMS_FILE = DATA_DIR / "items.jsonl"
ITEM_LIFECYCLE_STATE_FILE = DATA_DIR / "item_lifecycle_state.json"
ITEM_VERSIONS_FILE = DATA_DIR / "item_versions.jsonl"
LIFECYCLE_EVENTS_FILE = DATA_DIR / "lifecycle_events.jsonl"
LIFECYCLE_REPORT_FILE = DATA_DIR / "lifecycle_report.json"

DEFAULT_LONG_ABSENCE_OBSERVATION_THRESHOLD = 4
DEFAULT_LONG_ABSENCE_MIN_DAYS = 14
DEFAULT_DETAIL_FAILURE_ATTENTION_THRESHOLD = 3
DEFAULT_MAX_ITEM_VERSIONS_PER_RECORD = 20
DEFAULT_MAX_LIFECYCLE_EVENTS = 1000

ALLOWED_LIFECYCLE_STATES = frozenset({"active", "temporarily_missing", "fetch_failed", "long_absent"})
ALLOWED_EVENT_TYPES = frozenset(
    {
        "lifecycle_initialized",
        "item_discovered",
        "semantic_content_changed",
        "extraction_improved",
        "extraction_degraded",
        "detail_fetch_failed",
        "detail_fetch_recovered",
        "temporarily_missing",
        "long_absence_reached",
        "reappeared",
        "unchanged_observation",
    }
)
ALLOWED_VERSION_KINDS = frozenset(
    {"initial_snapshot", "new_item", "semantic_change", "extraction_improvement"}
)
MEANINGFUL_EVENT_TYPES = ALLOWED_EVENT_TYPES - {"lifecycle_initialized", "unchanged_observation"}
QUALITY_RANK = {"unknown": 0, "low": 1, "medium": 2, "high": 3}
EXCERPT_LIMIT = 240
EVIDENCE_EXCERPT_LIMIT = 800


@dataclass
class LifecycleUpdatePlan:
    updated_items: list[dict[str, Any]]
    updated_lifecycle_state: dict[str, Any]
    all_versions: list[dict[str, Any]]
    all_lifecycle_events: list[dict[str, Any]]
    new_versions: list[dict[str, Any]]
    new_lifecycle_events: list[dict[str, Any]]
    lifecycle_report: dict[str, Any]
    warnings: list[str] = field(default_factory=list)
    ignored_as_stale: bool = False
    duplicate_run: bool = False


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def safe_positive_int(value: object, default: int, name: str, warnings: list[str] | None = None) -> int:
    raw = "" if value is None else str(value).strip()
    try:
        parsed = int(raw)
    except (TypeError, ValueError):
        parsed = default
    if parsed < 1:
        parsed = default
    if warnings is not None and raw and parsed == default and raw != str(default):
        warnings.append(f"{name} 配置无效，已使用安全默认值 {default}。")
    return parsed


def normalize_semantic_text(value: str | None) -> str:
    if value is None:
        return ""
    text = html.unescape(str(value))
    text = unicodedata.normalize("NFKC", text)
    text = text.translate(
        str.maketrans(
            {
                "\u2018": "'",
                "\u2019": "'",
                "\u201c": '"',
                "\u201d": '"',
                "\u2013": "-",
                "\u2014": "-",
                "\u00a0": " ",
            }
        )
    )
    return " ".join(text.replace("\r\n", "\n").replace("\r", "\n").split())


def _normalize_fact_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _normalize_fact_value(value[key]) for key in sorted(value, key=str)}
    if isinstance(value, list):
        return [_normalize_fact_value(item) for item in value]
    if isinstance(value, tuple):
        return [_normalize_fact_value(item) for item in value]
    if isinstance(value, str):
        return normalize_semantic_text(value) or None
    return value


def build_semantic_payload(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": normalize_semantic_text(record.get("title")) or None,
        "published_at": normalize_semantic_text(record.get("published_at")) or None,
        "modified_at": normalize_semantic_text(record.get("modified_at")) or None,
        "summary": normalize_semantic_text(record.get("summary")) or None,
        "evidence": normalize_semantic_text(record.get("evidence")) or None,
        "structured_fields": _normalize_fact_value(record.get("structured_fields") or {}),
    }


def _canonical_hash(payload: dict[str, Any], length: int = 16) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:length]


def semantic_content_hash(record: dict[str, Any]) -> str:
    return _canonical_hash(build_semantic_payload(record))


def _field_completeness(record: dict[str, Any]) -> dict[str, bool]:
    payload = build_semantic_payload(record)
    return {
        "title": bool(payload["title"]),
        "published_at": bool(payload["published_at"]),
        "modified_at": bool(payload["modified_at"]),
        "summary": bool(payload["summary"]),
        "evidence": bool(payload["evidence"]),
        "structured_fields": bool(payload["structured_fields"]),
    }


def build_extraction_payload(record: dict[str, Any]) -> dict[str, Any]:
    confidence = record.get("extraction_confidence")
    try:
        confidence = round(float(confidence), 4) if confidence is not None else None
    except (TypeError, ValueError):
        confidence = None
    return {
        "parser_version": normalize_semantic_text(record.get("parser_version")) or None,
        "field_evidence": _normalize_fact_value(record.get("field_evidence") or {}),
        "source_quality": normalize_semantic_text(record.get("source_quality")) or None,
        "extraction_confidence": confidence,
        "detail_parse_method": normalize_semantic_text(record.get("detail_parse_method")) or None,
        "field_completeness": _field_completeness(record),
    }


def extraction_content_hash(record: dict[str, Any]) -> str:
    return _canonical_hash(build_extraction_payload(record))


def _is_empty(value: Any) -> bool:
    return value in (None, "", [], {})


def _flatten(value: Any, prefix: str = "") -> dict[str, Any]:
    if isinstance(value, dict):
        flattened: dict[str, Any] = {}
        for key in sorted(value, key=str):
            child = f"{prefix}.{key}" if prefix else str(key)
            flattened.update(_flatten(value[key], child))
        if not value and prefix:
            flattened[prefix] = {}
        return flattened
    return {prefix: value}


def _excerpt(value: Any, limit: int = EXCERPT_LIMIT) -> str | None:
    if _is_empty(value):
        return None
    if isinstance(value, (dict, list)):
        text = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    else:
        text = normalize_semantic_text(str(value))
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _is_non_conflicting_growth(field: str, before: Any, after: Any) -> bool:
    if field not in {"summary", "evidence"} or not isinstance(before, str) or not isinstance(after, str):
        return False
    old = normalize_semantic_text(before).casefold()
    new = normalize_semantic_text(after).casefold()
    return bool(old and new and old != new and old in new)


def compare_semantic_versions(previous: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    before = _flatten(build_semantic_payload(previous))
    after = _flatten(build_semantic_payload(current))
    changed_fields: list[str] = []
    improved_fields: list[str] = []
    degraded_fields: list[str] = []
    change_evidence: dict[str, dict[str, str | None]] = {}

    for field in sorted(set(before) | set(after)):
        old_value = before.get(field)
        new_value = after.get(field)
        if old_value == new_value:
            continue
        if _is_empty(old_value) and not _is_empty(new_value):
            improved_fields.append(field)
            continue
        if not _is_empty(old_value) and _is_empty(new_value):
            degraded_fields.append(field)
            continue
        if _is_non_conflicting_growth(field, old_value, new_value):
            improved_fields.append(field)
            continue
        changed_fields.append(field)
        change_evidence[field] = {
            "before_excerpt": _excerpt(old_value),
            "after_excerpt": _excerpt(new_value),
        }

    return {
        "semantic_changed": bool(changed_fields),
        "changed_fields": changed_fields,
        "change_evidence": change_evidence,
        "improved_fields": improved_fields,
        "degraded_fields": degraded_fields,
        "previous_semantic_hash": semantic_content_hash(previous),
        "current_semantic_hash": semantic_content_hash(current),
    }


def compare_extraction_versions(
    previous: dict[str, Any],
    current: dict[str, Any],
    semantic_comparison: dict[str, Any] | None = None,
) -> dict[str, Any]:
    semantic_comparison = semantic_comparison or compare_semantic_versions(previous, current)
    improved_reasons = list(semantic_comparison.get("improved_fields") or [])
    degraded_reasons = list(semantic_comparison.get("degraded_fields") or [])
    old_payload = build_extraction_payload(previous)
    new_payload = build_extraction_payload(current)

    old_evidence = old_payload["field_evidence"] if isinstance(old_payload["field_evidence"], dict) else {}
    new_evidence = new_payload["field_evidence"] if isinstance(new_payload["field_evidence"], dict) else {}
    for key, value in new_evidence.items():
        if not _is_empty(value) and _is_empty(old_evidence.get(key)):
            improved_reasons.append(f"field_evidence.{key}")
    for key, value in old_evidence.items():
        if not _is_empty(value) and _is_empty(new_evidence.get(key)):
            degraded_reasons.append(f"field_evidence.{key}")

    # Parser or method metadata alone changes the extraction hash but is not an
    # improvement unless factual completeness or evidence also improves.

    old_quality = QUALITY_RANK.get(str(old_payload["source_quality"] or "unknown").lower(), 0)
    new_quality = QUALITY_RANK.get(str(new_payload["source_quality"] or "unknown").lower(), 0)
    if new_quality > old_quality:
        improved_reasons.append("source_quality")
    elif new_quality < old_quality:
        degraded_reasons.append("source_quality")

    old_confidence = old_payload["extraction_confidence"]
    new_confidence = new_payload["extraction_confidence"]
    if old_confidence is not None and new_confidence is not None:
        if new_confidence > old_confidence:
            improved_reasons.append("extraction_confidence")
        elif new_confidence < old_confidence:
            degraded_reasons.append("extraction_confidence")

    improved_reasons = sorted(set(improved_reasons))
    degraded_reasons = sorted(set(degraded_reasons) - set(improved_reasons))
    if improved_reasons:
        status = "improved"
    elif degraded_reasons:
        status = "degraded"
    else:
        status = "unchanged"
    return {
        "status": status,
        "improved_reasons": improved_reasons,
        "degraded_reasons": degraded_reasons,
        "previous_extraction_hash": extraction_content_hash(previous),
        "current_extraction_hash": extraction_content_hash(current),
    }


def load_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return deepcopy(default)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return deepcopy(default)
    return value if isinstance(value, dict) else deepcopy(default)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as file:
        for line in file:
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                records.append(value)
    return records


def load_lifecycle_state(path: Path = ITEM_LIFECYCLE_STATE_FILE) -> dict[str, Any]:
    return load_json(path, {"version": 1, "stage": "4D", "generated_at": None, "migration": {}, "items": {}})


def load_lifecycle_report(path: Path = LIFECYCLE_REPORT_FILE) -> dict[str, Any]:
    return load_json(path, {"version": 1, "stage": "4D", "generated_at": None, "totals": {}, "sources": {}})


def _parse_datetime(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        if text.endswith(("Z", "z")):
            text = text[:-1] + "+00:00"
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed


def _deterministic_observed_at(
    previous_items: list[dict[str, Any]], merged_items: list[dict[str, Any]]
) -> str:
    candidates: list[datetime] = []
    for record in [*previous_items, *merged_items]:
        for key in ("last_seen_at", "last_detail_attempt_at", "first_seen_at"):
            parsed = _parse_datetime(record.get(key))
            if parsed is not None:
                candidates.append(parsed)
    selected = max(candidates) if candidates else datetime(1970, 1, 1, tzinfo=timezone.utc)
    return selected.astimezone(timezone.utc).isoformat(timespec="seconds")


def classify_run_order(
    *,
    run_id: str,
    started_at: str,
    last_applied_run_id: object,
    last_applied_started_at: object,
) -> str:
    """Return current, duplicate, stale, or invalid without reading external state."""
    if str(last_applied_run_id or "") == run_id:
        return "duplicate"
    current = _parse_datetime(started_at)
    previous = _parse_datetime(last_applied_started_at)
    if current is None:
        return "invalid"
    if previous is not None and current <= previous:
        return "stale"
    return "current"


def _days_since(value: object, observed_at: str) -> int:
    start = _parse_datetime(value)
    end = _parse_datetime(observed_at)
    if start is None or end is None:
        return 0
    return max(0, (end - start).days)


def _version_id(record_id: str, semantic_hash: str, extraction_hash: str) -> str:
    return hashlib.sha256(f"{record_id}|{semantic_hash}|{extraction_hash}".encode("utf-8")).hexdigest()[:20]


def _event_id(run_id: str, record_id: str, event_type: str) -> str:
    return hashlib.sha256(f"{run_id}|{record_id}|{event_type}".encode("utf-8")).hexdigest()[:20]


def _limited_mapping(value: object, value_limit: int = EXCERPT_LIMIT) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    limited: dict[str, Any] = {}
    for key in sorted(value, key=str):
        item = value[key]
        if isinstance(item, dict):
            limited[str(key)] = _limited_mapping(item, value_limit)
        elif isinstance(item, list):
            limited[str(key)] = [_excerpt(entry, value_limit) for entry in item[:20]]
        else:
            limited[str(key)] = _excerpt(item, value_limit)
    return limited


def _build_version(
    record: dict[str, Any],
    state: dict[str, Any],
    version_kind: str,
    observed_at: str,
    run_id: str,
    changed_fields: Iterable[str] = (),
) -> dict[str, Any]:
    semantic_hash = str(state["current_semantic_hash"])
    extraction_hash = str(state["current_extraction_hash"])
    record_id = str(record["id"])
    return {
        "version_id": _version_id(record_id, semantic_hash, extraction_hash),
        "run_id": run_id,
        "record_id": record_id,
        "source_id": record.get("source_id"),
        "source_name": record.get("source_name") or record.get("source_id"),
        "title": _excerpt(record.get("title"), 300),
        "canonical_url": record.get("canonical_url") or record.get("url"),
        "observed_at": observed_at,
        "version_kind": version_kind,
        "semantic_version": int(state["semantic_version"]),
        "extraction_revision": int(state["extraction_revision"]),
        "semantic_hash": semantic_hash,
        "extraction_hash": extraction_hash,
        "title": _excerpt(record.get("title"), 300),
        "published_at": record.get("published_at"),
        "modified_at": record.get("modified_at"),
        "summary": _excerpt(record.get("summary"), 500),
        "evidence_excerpt": _excerpt(record.get("evidence"), EVIDENCE_EXCERPT_LIMIT),
        "structured_fields": _limited_mapping(record.get("structured_fields"), 300),
        "field_evidence": _limited_mapping(record.get("field_evidence"), 300),
        "parser_version": record.get("parser_version"),
        "source_quality": record.get("source_quality"),
        "extraction_confidence": record.get("extraction_confidence"),
        "changed_fields": sorted(set(str(field) for field in changed_fields if field)),
    }


def _build_event(
    *,
    run_id: str,
    observed_at: str,
    event_type: str,
    record: dict[str, Any],
    previous_state: str,
    current_state: str,
    change_status: str,
    extraction_change_status: str,
    previous_semantic_hash: str | None,
    current_semantic_hash: str | None,
    changed_fields: Iterable[str] = (),
    change_evidence: dict[str, Any] | None = None,
    reason: str | None = None,
    attention_required: bool = False,
) -> dict[str, Any]:
    event_type = str(event_type)
    record_id = str(record.get("id") or "")
    return {
        "event_id": _event_id(run_id, record_id, event_type),
        "run_id": run_id,
        "occurred_at": observed_at,
        "event_type": event_type,
        "record_id": record_id,
        "source_id": record.get("source_id"),
        "canonical_url": record.get("canonical_url") or record.get("url"),
        "previous_lifecycle_state": previous_state,
        "current_lifecycle_state": current_state,
        "change_status": change_status,
        "extraction_change_status": extraction_change_status,
        "previous_semantic_hash": previous_semantic_hash,
        "current_semantic_hash": current_semantic_hash,
        "changed_fields": sorted(set(str(field) for field in changed_fields if field)),
        "change_evidence": deepcopy(change_evidence or {}),
        "reason": reason or event_type,
        "attention_required": bool(attention_required),
    }


def _new_state(record: dict[str, Any], observed_at: str) -> dict[str, Any]:
    first_observed = record.get("first_seen_at") or record.get("last_seen_at") or observed_at
    semantic_hash = semantic_content_hash(record)
    extraction_hash = extraction_content_hash(record)
    return {
        "record_id": record.get("id"),
        "source_id": record.get("source_id"),
        "canonical_url": record.get("canonical_url") or record.get("url"),
        "title": _excerpt(record.get("title"), 300),
        "lifecycle_state": "active",
        "first_observed_at": first_observed,
        "last_index_seen_at": record.get("last_seen_at") or observed_at,
        "last_detail_attempt_at": record.get("last_detail_attempt_at") or observed_at,
        "last_detail_success_at": record.get("last_detail_success_at") or record.get("last_seen_at") or observed_at,
        "last_semantic_change_at": None,
        "last_extraction_improvement_at": None,
        "missing_since": None,
        "consecutive_missing_observations": 0,
        "consecutive_detail_failures": 0,
        "last_error_type": None,
        "semantic_version": 1,
        "extraction_revision": 1,
        "current_semantic_hash": semantic_hash,
        "current_extraction_hash": extraction_hash,
        "last_lifecycle_event": None,
        "attention_required": False,
    }


def _apply_state_to_item(record: dict[str, Any], state: dict[str, Any]) -> None:
    if record.get("change_status"):
        state["change_status"] = record.get("change_status")
    if record.get("extraction_change_status"):
        state["extraction_change_status"] = record.get("extraction_change_status")
    for key in (
        "lifecycle_state",
        "semantic_version",
        "extraction_revision",
        "last_semantic_change_at",
        "last_extraction_improvement_at",
        "missing_since",
        "consecutive_missing_observations",
        "consecutive_detail_failures",
        "last_lifecycle_event",
        "attention_required",
    ):
        record[key] = state.get(key)
    record["semantic_content_hash"] = state.get("current_semantic_hash")
    record["content_hash"] = state.get("current_semantic_hash")
    record["extraction_hash"] = state.get("current_extraction_hash")


def _source_complete(observations: dict[str, dict[str, Any]], source_id: str) -> bool:
    observation = observations.get(source_id, {})
    return bool(observation.get("index_observation_complete"))


def _source_observed(observations: dict[str, dict[str, Any]], source_id: str) -> bool:
    return source_id in observations


def _is_detail_failure(record: dict[str, Any]) -> bool:
    detail_status = str(record.get("detail_fetch_status") or "").lower()
    if detail_status == "success" and record.get("current_run_data_reused") is not True:
        return False
    return bool(
        record.get("current_run_data_reused")
        or detail_status in {"failed", "failed_this_run"}
        or str(record.get("extraction_change_status") or "").lower() == "failed"
    )


def _deduplicate(records: Iterable[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    selected: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for record in records:
        identity = str(record.get(key) or "")
        if not identity:
            continue
        if identity not in selected:
            order.append(identity)
        selected[identity] = record
    return [selected[identity] for identity in order]


def _trim_versions(records: list[dict[str, Any]], max_per_record: int) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    record_order: list[str] = []
    for record in records:
        record_id = str(record.get("record_id") or "")
        if record_id not in grouped:
            grouped[record_id] = []
            record_order.append(record_id)
        grouped[record_id].append(record)
    trimmed: list[dict[str, Any]] = []
    for record_id in record_order:
        trimmed.extend(grouped[record_id][-max_per_record:])
    return trimmed


def _initialize_existing_records(
    records_by_id: dict[str, dict[str, Any]],
    previous_item_ids: set[str],
    state_items: dict[str, dict[str, Any]],
    run_id: str,
    observed_at: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], set[str]]:
    versions: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    initialized: set[str] = set()
    for record_id in sorted(previous_item_ids):
        record = records_by_id.get(record_id)
        if not record or record.get("record_scope") != "item" or record_id in state_items:
            continue
        state = _new_state(record, observed_at)
        state["last_lifecycle_event"] = "lifecycle_initialized"
        state_items[record_id] = state
        record["change_status"] = "unchanged"
        record["extraction_change_status"] = "unchanged"
        record["change_reason"] = "phase4c_lifecycle_initialized"
        record["lifecycle_events_this_run"] = []
        record["semantic_change_evidence"] = {}
        _apply_state_to_item(record, state)
        versions.append(_build_version(record, state, "initial_snapshot", observed_at, run_id))
        events.append(
            _build_event(
                run_id=run_id,
                observed_at=observed_at,
                event_type="lifecycle_initialized",
                record=record,
                previous_state="uninitialized",
                current_state="active",
                change_status="unchanged",
                extraction_change_status="unchanged",
                previous_semantic_hash=None,
                current_semantic_hash=state["current_semantic_hash"],
                reason="phase4c_existing_item_migration",
            )
        )
        initialized.add(record_id)
    return versions, events, initialized


def _ignored_lifecycle_plan(
    *,
    previous_items: list[dict[str, Any]],
    lifecycle_state: dict[str, Any] | None,
    existing_versions: list[dict[str, Any]] | None,
    existing_events: list[dict[str, Any]] | None,
    run_id: str,
    observed_at: str,
    reason: str,
) -> LifecycleUpdatePlan:
    state_document = deepcopy(
        lifecycle_state
        or {"version": 1, "stage": "4D", "generated_at": None, "migration": {}, "items": {}}
    )
    state_items = state_document.get("items", {}) if isinstance(state_document.get("items"), dict) else {}
    sources: dict[str, dict[str, Any]] = {}
    for item in state_items.values():
        source_id = str(item.get("source_id") or "")
        if not source_id:
            continue
        source = sources.setdefault(
            source_id,
            {
                "source_id": source_id,
                "source_name": source_id,
                "active": 0,
                "temporarily_missing": 0,
                "long_absent": 0,
                "fetch_failed": 0,
                "new": 0,
                "changed": 0,
                "extraction_improved": 0,
                "recovered": 0,
                "reappeared": 0,
                "attention": 0,
            },
        )
        lifecycle_name = str(item.get("lifecycle_state") or "active")
        if lifecycle_name in source:
            source[lifecycle_name] += 1
        if item.get("attention_required") is True:
            source["attention"] += 1
    totals = {
        "initialized": 0,
        "new": 0,
        "changed": 0,
        "extraction_improved": 0,
        "temporarily_missing": 0,
        "long_absent": 0,
        "detail_fetch_failed": 0,
        "recovered_after_failure": 0,
        "reappeared": 0,
        "unchanged": len(state_items),
        "new_semantic_versions": 0,
        "new_extraction_revisions": 0,
        "lifecycle_events": 0,
    }
    warning = (
        "检测到重复 run_id，生命周期更新已幂等跳过。"
        if reason == "duplicate_run"
        else "检测到旧运行或无法安全解析的运行时间，生命周期状态未被覆盖。"
    )
    report = {
        "version": 1,
        "stage": "4D",
        "generated_at": observed_at,
        "run_id": run_id,
        "totals": totals,
        "sources": sources,
        "attention_items": [],
        "events_this_run": [],
        "versions_this_run": [],
        "stale_run_ignored": reason != "duplicate_run",
        "duplicate_run_ignored": reason == "duplicate_run",
        "warnings": [warning],
    }
    return LifecycleUpdatePlan(
        updated_items=deepcopy(previous_items),
        updated_lifecycle_state=state_document,
        all_versions=deepcopy(existing_versions or []),
        all_lifecycle_events=deepcopy(existing_events or []),
        new_versions=[],
        new_lifecycle_events=[],
        lifecycle_report=report,
        warnings=[warning],
        ignored_as_stale=reason != "duplicate_run",
        duplicate_run=reason == "duplicate_run",
    )


def build_lifecycle_update_plan(
    previous_items: list[dict[str, Any]],
    merged_items: list[dict[str, Any]],
    source_observations: dict[str, dict[str, Any]],
    *,
    lifecycle_state: dict[str, Any] | None = None,
    existing_versions: list[dict[str, Any]] | None = None,
    existing_events: list[dict[str, Any]] | None = None,
    run_id: str | None = None,
    observed_at: str | None = None,
    long_absence_observation_threshold: int = DEFAULT_LONG_ABSENCE_OBSERVATION_THRESHOLD,
    long_absence_min_days: int = DEFAULT_LONG_ABSENCE_MIN_DAYS,
    detail_failure_attention_threshold: int = DEFAULT_DETAIL_FAILURE_ATTENTION_THRESHOLD,
    max_item_versions_per_record: int = DEFAULT_MAX_ITEM_VERSIONS_PER_RECORD,
    max_lifecycle_events: int = DEFAULT_MAX_LIFECYCLE_EVENTS,
) -> LifecycleUpdatePlan:
    """Build a deterministic lifecycle plan without network, environment, or file I/O."""
    if observed_at is None:
        previous_started = _parse_datetime((lifecycle_state or {}).get("last_applied_started_at"))
        observed_at = (
            (previous_started + timedelta(seconds=1)).isoformat(timespec="seconds")
            if previous_started is not None
            else _deterministic_observed_at(previous_items, merged_items)
        )
    run_id = run_id or hashlib.sha256(observed_at.encode("utf-8")).hexdigest()[:16]
    long_absence_observation_threshold = max(1, int(long_absence_observation_threshold))
    long_absence_min_days = max(1, int(long_absence_min_days))
    detail_failure_attention_threshold = max(1, int(detail_failure_attention_threshold))
    max_item_versions_per_record = max(1, int(max_item_versions_per_record))
    max_lifecycle_events = max(1, int(max_lifecycle_events))

    previous_state_document = lifecycle_state or {}
    run_order = classify_run_order(
        run_id=run_id,
        started_at=observed_at,
        last_applied_run_id=previous_state_document.get("last_applied_run_id"),
        last_applied_started_at=previous_state_document.get("last_applied_started_at"),
    )
    if run_order in {"duplicate", "stale", "invalid"}:
        return _ignored_lifecycle_plan(
            previous_items=previous_items,
            lifecycle_state=lifecycle_state,
            existing_versions=existing_versions,
            existing_events=existing_events,
            run_id=run_id,
            observed_at=observed_at,
            reason="duplicate_run" if run_order == "duplicate" else "stale_run",
        )

    updated_items = deepcopy(merged_items)
    records_by_id = {
        str(record.get("id")): record
        for record in updated_items
        if record.get("id") and record.get("record_scope") == "item"
    }
    previous_by_id = {
        str(record.get("id")): deepcopy(record)
        for record in previous_items
        if record.get("id") and record.get("record_scope") == "item"
    }
    state_document = deepcopy(
        lifecycle_state
        or {"version": 1, "stage": "4D", "generated_at": None, "migration": {}, "items": {}}
    )
    state_document["version"] = 1
    state_document["stage"] = "4D"
    state_document["generated_at"] = observed_at
    state_document["run_id"] = run_id
    state_document["last_applied_run_id"] = run_id
    state_document["last_applied_started_at"] = observed_at
    state_items = state_document.setdefault("items", {})
    if not isinstance(state_items, dict):
        raise ValueError("item_lifecycle_state.json 的 items 必须是 object。")

    new_versions: list[dict[str, Any]] = []
    new_events: list[dict[str, Any]] = []
    migration = state_document.setdefault("migration", {})
    migrated_ids: set[str] = set()
    if not migration.get("phase4c_initialized"):
        initial_versions, initial_events, migrated_ids = _initialize_existing_records(
            records_by_id,
            set(previous_by_id),
            state_items,
            run_id,
            observed_at,
        )
        new_versions.extend(initial_versions)
        new_events.extend(initial_events)
        migration.update(
            {
                "phase4c_initialized": True,
                "initialized_at": observed_at,
                "initialized_item_count": len(migrated_ids),
            }
        )

    report_events: list[dict[str, Any]] = []
    unchanged_count = len(migrated_ids)
    for record_id in sorted(set(state_items) | set(records_by_id)):
        record = records_by_id.get(record_id)
        state = state_items.get(record_id)
        if record_id in migrated_ids:
            continue
        if record is None or record.get("record_scope") != "item":
            continue
        source_id = str(record.get("source_id") or "")
        observed_source = _source_observed(source_observations, source_id)
        present = observed_source and record.get("seen_in_current_index") is not False
        complete = _source_complete(source_observations, source_id)
        record_events: list[str] = []
        semantic_evidence: dict[str, Any] = {}

        if state is None:
            if not present:
                continue
            state = _new_state(record, observed_at)
            state["last_lifecycle_event"] = "item_discovered"
            state_items[record_id] = state
            record["change_status"] = "new"
            record["extraction_change_status"] = "unchanged"
            record["change_reason"] = "item_discovered"
            event = _build_event(
                run_id=run_id,
                observed_at=observed_at,
                event_type="item_discovered",
                record=record,
                previous_state="unobserved",
                current_state="active",
                change_status="new",
                extraction_change_status="unchanged",
                previous_semantic_hash=None,
                current_semantic_hash=state["current_semantic_hash"],
                reason="first_observed_source_id_and_canonical_url",
            )
            new_events.append(event)
            report_events.append(event)
            record_events.append("item_discovered")
            new_versions.append(_build_version(record, state, "new_item", observed_at, run_id))
            record["lifecycle_events_this_run"] = record_events
            record["semantic_change_evidence"] = {}
            _apply_state_to_item(record, state)
            continue

        previous_state_name = str(state.get("lifecycle_state") or "active")
        previous_semantic_hash = str(state.get("current_semantic_hash") or semantic_content_hash(previous_by_id.get(record_id, record)))
        state["title"] = _excerpt(record.get("title"), 300)
        state["canonical_url"] = record.get("canonical_url") or record.get("url")

        if not observed_source:
            _apply_state_to_item(record, state)
            continue

        if not present:
            if not complete:
                _apply_state_to_item(record, state)
                continue
            missing_count = int(state.get("consecutive_missing_observations") or 0) + 1
            state["consecutive_missing_observations"] = missing_count
            state["consecutive_detail_failures"] = 0
            state["last_error_type"] = None
            state["attention_required"] = False
            if not state.get("missing_since"):
                state["missing_since"] = observed_at
            reaches_long_absence = (
                missing_count >= long_absence_observation_threshold
                and _days_since(state.get("missing_since"), observed_at) >= long_absence_min_days
            )
            if reaches_long_absence:
                state["lifecycle_state"] = "long_absent"
                if previous_state_name != "long_absent":
                    event_type = "long_absence_reached"
                else:
                    event_type = None
            else:
                state["lifecycle_state"] = "temporarily_missing"
                if previous_state_name not in {"temporarily_missing", "long_absent"}:
                    event_type = "temporarily_missing"
                else:
                    event_type = None
            record["change_status"] = "unchanged"
            record["extraction_change_status"] = "unchanged"
            record["change_reason"] = "index_candidate_not_observed"
            if event_type:
                state["last_lifecycle_event"] = event_type
                event = _build_event(
                    run_id=run_id,
                    observed_at=observed_at,
                    event_type=event_type,
                    record=record,
                    previous_state=previous_state_name,
                    current_state=state["lifecycle_state"],
                    change_status="unchanged",
                    extraction_change_status="unchanged",
                    previous_semantic_hash=previous_semantic_hash,
                    current_semantic_hash=previous_semantic_hash,
                    reason="absent_from_complete_index_observation",
                )
                event["index_observation_complete"] = True
                new_events.append(event)
                report_events.append(event)
                record_events.append(event_type)
            else:
                unchanged_count += 1
            record["lifecycle_events_this_run"] = record_events
            record["semantic_change_evidence"] = {}
            _apply_state_to_item(record, state)
            continue

        state["last_index_seen_at"] = record.get("last_seen_at") or observed_at
        state["consecutive_missing_observations"] = 0
        state["missing_since"] = None
        if previous_state_name in {"temporarily_missing", "long_absent"}:
            event = _build_event(
                run_id=run_id,
                observed_at=observed_at,
                event_type="reappeared",
                record=record,
                previous_state=previous_state_name,
                current_state="active",
                change_status="unchanged",
                extraction_change_status="unchanged",
                previous_semantic_hash=previous_semantic_hash,
                current_semantic_hash=semantic_content_hash(record),
                reason="historical_item_reappeared_in_index",
            )
            new_events.append(event)
            report_events.append(event)
            record_events.append("reappeared")

        if _is_detail_failure(record):
            failure_count = int(state.get("consecutive_detail_failures") or 0) + 1
            state["lifecycle_state"] = "fetch_failed"
            state["consecutive_detail_failures"] = failure_count
            state["last_detail_attempt_at"] = record.get("last_detail_attempt_at") or observed_at
            state["last_error_type"] = record.get("last_detail_error_type") or "unknown_error"
            state["attention_required"] = failure_count >= detail_failure_attention_threshold
            state["last_lifecycle_event"] = "detail_fetch_failed"
            record["change_status"] = "unchanged"
            record["extraction_change_status"] = "failed"
            record["change_reason"] = "detail_fetch_failed_reused_previous_success"
            event = _build_event(
                run_id=run_id,
                observed_at=observed_at,
                event_type="detail_fetch_failed",
                record=record,
                previous_state=previous_state_name,
                current_state="fetch_failed",
                change_status="unchanged",
                extraction_change_status="failed",
                previous_semantic_hash=previous_semantic_hash,
                current_semantic_hash=previous_semantic_hash,
                reason="collector_detail_fetch_failed_historical_data_retained",
                attention_required=state["attention_required"],
            )
            new_events.append(event)
            report_events.append(event)
            record_events.append("detail_fetch_failed")
            record["lifecycle_events_this_run"] = record_events
            record["semantic_change_evidence"] = {}
            _apply_state_to_item(record, state)
            continue

        state["lifecycle_state"] = "active"
        state["last_detail_attempt_at"] = record.get("last_detail_attempt_at") or observed_at
        state["last_detail_success_at"] = record.get("last_detail_success_at") or observed_at
        state["last_error_type"] = None
        state["attention_required"] = False
        if previous_state_name == "fetch_failed" or int(state.get("consecutive_detail_failures") or 0) > 0:
            event = _build_event(
                run_id=run_id,
                observed_at=observed_at,
                event_type="detail_fetch_recovered",
                record=record,
                previous_state=previous_state_name,
                current_state="active",
                change_status="unchanged",
                extraction_change_status="unchanged",
                previous_semantic_hash=previous_semantic_hash,
                current_semantic_hash=semantic_content_hash(record),
                reason="collector_detail_fetch_recovered",
            )
            new_events.append(event)
            report_events.append(event)
            record_events.append("detail_fetch_recovered")
        state["consecutive_detail_failures"] = 0

        previous_record = previous_by_id.get(record_id, record)
        semantic_comparison = compare_semantic_versions(previous_record, record)
        extraction_comparison = compare_extraction_versions(previous_record, record, semantic_comparison)
        current_semantic_hash = semantic_comparison["current_semantic_hash"]
        current_extraction_hash = extraction_comparison["current_extraction_hash"]
        state["current_semantic_hash"] = current_semantic_hash
        state["current_extraction_hash"] = current_extraction_hash

        semantic_changed = bool(semantic_comparison["semantic_changed"])
        extraction_status = str(extraction_comparison["status"])
        if semantic_changed:
            state["semantic_version"] = int(state.get("semantic_version") or 1) + 1
            state["last_semantic_change_at"] = observed_at
            state["last_lifecycle_event"] = "semantic_content_changed"
            record["change_status"] = "changed"
            record["change_reason"] = "semantic_content_changed"
            semantic_evidence = deepcopy(semantic_comparison["change_evidence"])
            event = _build_event(
                run_id=run_id,
                observed_at=observed_at,
                event_type="semantic_content_changed",
                record=record,
                previous_state=previous_state_name,
                current_state="active",
                change_status="changed",
                extraction_change_status=extraction_status,
                previous_semantic_hash=previous_semantic_hash,
                current_semantic_hash=current_semantic_hash,
                changed_fields=semantic_comparison["changed_fields"],
                change_evidence=semantic_evidence,
                reason="semantic_content_changed",
                attention_required=True,
            )
            new_events.append(event)
            report_events.append(event)
            record_events.append("semantic_content_changed")
        else:
            record["change_status"] = "unchanged"
            record["change_reason"] = "no_semantic_change"

        if extraction_status == "improved":
            state["extraction_revision"] = int(state.get("extraction_revision") or 1) + 1
            state["last_extraction_improvement_at"] = observed_at
            state["last_lifecycle_event"] = "extraction_improved"
            record["extraction_change_status"] = "improved"
            if not semantic_changed:
                record["change_reason"] = "extraction_improved_without_semantic_change"
            event = _build_event(
                run_id=run_id,
                observed_at=observed_at,
                event_type="extraction_improved",
                record=record,
                previous_state=previous_state_name,
                current_state="active",
                change_status="unchanged",
                extraction_change_status="improved",
                previous_semantic_hash=previous_semantic_hash,
                current_semantic_hash=current_semantic_hash,
                changed_fields=extraction_comparison["improved_reasons"],
                reason="extraction_completeness_improved_not_official_fact_change",
            )
            new_events.append(event)
            report_events.append(event)
            record_events.append("extraction_improved")
        elif extraction_status == "degraded":
            state["last_lifecycle_event"] = "extraction_degraded"
            record["extraction_change_status"] = "degraded"
            event = _build_event(
                run_id=run_id,
                observed_at=observed_at,
                event_type="extraction_degraded",
                record=record,
                previous_state=previous_state_name,
                current_state="active",
                change_status=record["change_status"],
                extraction_change_status="degraded",
                previous_semantic_hash=previous_semantic_hash,
                current_semantic_hash=current_semantic_hash,
                changed_fields=extraction_comparison["degraded_reasons"],
                reason="extraction_completeness_degraded",
            )
            new_events.append(event)
            report_events.append(event)
            record_events.append("extraction_degraded")
        else:
            record["extraction_change_status"] = "unchanged"

        if semantic_changed or extraction_status == "improved":
            kind = "semantic_change" if semantic_changed else "extraction_improvement"
            changed_fields = (
                semantic_comparison["changed_fields"]
                if semantic_changed
                else extraction_comparison["improved_reasons"]
            )
            new_versions.append(_build_version(record, state, kind, observed_at, run_id, changed_fields))
        if not record_events:
            unchanged_count += 1
        record["lifecycle_events_this_run"] = record_events
        record["semantic_change_evidence"] = semantic_evidence
        _apply_state_to_item(record, state)

    for record_id, state in state_items.items():
        state["last_applied_run_id"] = run_id
        state["last_applied_started_at"] = observed_at
        record = records_by_id.get(record_id)
        if record is not None:
            _apply_state_to_item(record, state)

    all_versions = _trim_versions(
        _deduplicate([*(existing_versions or []), *new_versions], "version_id"),
        max_item_versions_per_record,
    )
    all_events = _deduplicate([*(existing_events or []), *new_events], "event_id")[-max_lifecycle_events:]
    existing_version_ids = {str(item.get("version_id")) for item in existing_versions or []}
    existing_event_ids = {str(item.get("event_id")) for item in existing_events or []}
    new_versions = [item for item in _deduplicate(new_versions, "version_id") if item["version_id"] not in existing_version_ids]
    new_events = [item for item in _deduplicate(new_events, "event_id") if item["event_id"] not in existing_event_ids]
    report_events = [item for item in new_events if item.get("event_type") in MEANINGFUL_EVENT_TYPES]

    totals = {
        "initialized": sum(1 for item in new_events if item.get("event_type") == "lifecycle_initialized"),
        "new": sum(1 for item in report_events if item.get("event_type") == "item_discovered"),
        "changed": sum(1 for item in report_events if item.get("event_type") == "semantic_content_changed"),
        "extraction_improved": sum(1 for item in report_events if item.get("event_type") == "extraction_improved"),
        "temporarily_missing": sum(1 for item in report_events if item.get("event_type") == "temporarily_missing"),
        "long_absent": sum(1 for item in report_events if item.get("event_type") == "long_absence_reached"),
        "detail_fetch_failed": sum(1 for item in report_events if item.get("event_type") == "detail_fetch_failed"),
        "recovered_after_failure": sum(1 for item in report_events if item.get("event_type") == "detail_fetch_recovered"),
        "reappeared": sum(1 for item in report_events if item.get("event_type") == "reappeared"),
        "unchanged": unchanged_count,
        "new_semantic_versions": sum(
            1 for item in new_versions if item.get("version_kind") in {"initial_snapshot", "new_item", "semantic_change"}
        ),
        "new_extraction_revisions": sum(
            1 for item in new_versions if item.get("version_kind") in {"initial_snapshot", "extraction_improvement"}
        ),
        "lifecycle_events": len(report_events),
    }

    source_names = {
        str(record.get("source_id") or ""): str(record.get("source_name") or record.get("source_id") or "")
        for record in records_by_id.values()
    }
    source_ids = sorted({str(item.get("source_id") or "") for item in state_items.values() if item.get("source_id")})
    sources: dict[str, dict[str, Any]] = {}
    for source_id in source_ids:
        source_states = [item for item in state_items.values() if item.get("source_id") == source_id]
        source_events = [item for item in report_events if item.get("source_id") == source_id]
        sources[source_id] = {
            "source_id": source_id,
            "source_name": source_names.get(source_id, source_id),
            "active": sum(1 for item in source_states if item.get("lifecycle_state") == "active"),
            "temporarily_missing": sum(1 for item in source_states if item.get("lifecycle_state") == "temporarily_missing"),
            "long_absent": sum(1 for item in source_states if item.get("lifecycle_state") == "long_absent"),
            "fetch_failed": sum(1 for item in source_states if item.get("lifecycle_state") == "fetch_failed"),
            "new": sum(1 for item in source_events if item.get("event_type") == "item_discovered"),
            "changed": sum(1 for item in source_events if item.get("event_type") == "semantic_content_changed"),
            "extraction_improved": sum(1 for item in source_events if item.get("event_type") == "extraction_improved"),
            "recovered": sum(1 for item in source_events if item.get("event_type") == "detail_fetch_recovered"),
            "reappeared": sum(1 for item in source_events if item.get("event_type") == "reappeared"),
            "attention": sum(1 for item in source_states if item.get("attention_required") is True),
        }

    attention_items = [
        {
            "record_id": item.get("record_id"),
            "source_id": item.get("source_id"),
            "canonical_url": item.get("canonical_url"),
            "lifecycle_state": item.get("lifecycle_state"),
            "consecutive_detail_failures": item.get("consecutive_detail_failures", 0),
        }
        for item in state_items.values()
        if item.get("attention_required") is True
    ]
    lifecycle_report = {
        "version": 1,
        "stage": "4D",
        "generated_at": observed_at,
        "run_id": run_id,
        "thresholds": {
            "long_absence_observation_threshold": long_absence_observation_threshold,
            "long_absence_min_days": long_absence_min_days,
            "detail_failure_attention_threshold": detail_failure_attention_threshold,
            "max_item_versions_per_record": max_item_versions_per_record,
            "max_lifecycle_events": max_lifecycle_events,
        },
        "totals": totals,
        "sources": sources,
        "attention_items": attention_items,
        "events_this_run": report_events,
        "versions_this_run": [
            {
                "version_id": item.get("version_id"),
                "record_id": item.get("record_id"),
                "source_id": item.get("source_id"),
                "canonical_url": item.get("canonical_url"),
                "version_kind": item.get("version_kind"),
                "semantic_version": item.get("semantic_version"),
                "extraction_revision": item.get("extraction_revision"),
                "observed_at": item.get("observed_at"),
                "changed_fields": item.get("changed_fields", []),
            }
            for item in new_versions
        ],
        "stale_run_ignored": False,
        "duplicate_run_ignored": False,
        "warnings": [],
    }

    validate_lifecycle_update_plan(
        LifecycleUpdatePlan(
            updated_items=updated_items,
            updated_lifecycle_state=state_document,
            all_versions=all_versions,
            all_lifecycle_events=all_events,
            new_versions=new_versions,
            new_lifecycle_events=new_events,
            lifecycle_report=lifecycle_report,
        )
    )
    return LifecycleUpdatePlan(
        updated_items=updated_items,
        updated_lifecycle_state=state_document,
        all_versions=all_versions,
        all_lifecycle_events=all_events,
        new_versions=new_versions,
        new_lifecycle_events=new_events,
        lifecycle_report=lifecycle_report,
    )


def apply_lifecycle_observation(
    *,
    previous_item: dict[str, Any] | None,
    previous_lifecycle_state: dict[str, Any] | None,
    observation: dict[str, Any],
    run_context: dict[str, Any],
    policy: dict[str, Any],
) -> dict[str, Any]:
    """Apply one offline observation through the same pure engine used in production."""
    run_id = str(run_context.get("run_id") or "")
    observed_at = str(run_context.get("started_at") or run_context.get("observed_at") or "")
    if not run_id or _parse_datetime(observed_at) is None:
        return {
            "updated_item": deepcopy(previous_item),
            "updated_lifecycle_state": deepcopy(previous_lifecycle_state),
            "new_versions": [],
            "new_events": [],
            "warnings": ["run_context 缺少可解析的 run_id 或 started_at，已安全拒绝。"],
            "ignored_as_stale": True,
            "duplicate_run": False,
        }

    current_record = deepcopy(observation.get("current_record") or previous_item)
    if current_record is None:
        raise ValueError("observation 必须提供 current_record 或 previous_item。")
    for key in ("source_id", "canonical_url", "record_id"):
        value = observation.get(key)
        if key == "record_id" and value:
            current_record["id"] = value
        elif value:
            current_record[key] = value
    current_record.setdefault("record_scope", "item")
    current_record["seen_in_current_index"] = bool(observation.get("seen_in_current_index"))
    if observation.get("detail_fetch_status"):
        current_record["detail_fetch_status"] = observation.get("detail_fetch_status")
    if observation.get("error_type"):
        current_record["last_detail_error_type"] = observation.get("error_type")
    if str(current_record.get("detail_fetch_status") or "").lower() in {"failed", "failed_this_run"}:
        current_record["current_run_data_reused"] = True

    source_id = str(current_record.get("source_id") or observation.get("source_id") or "")
    state_document: dict[str, Any] = {
        "version": 1,
        "stage": "4D",
        "migration": {"phase4c_initialized": True},
        "items": {},
    }
    if previous_lifecycle_state:
        record_id = str(current_record.get("id") or "")
        state_document["items"][record_id] = deepcopy(previous_lifecycle_state)
        state_document["last_applied_run_id"] = previous_lifecycle_state.get("last_applied_run_id")
        state_document["last_applied_started_at"] = previous_lifecycle_state.get("last_applied_started_at")
    previous_items = [deepcopy(previous_item)] if previous_item else []
    plan = build_lifecycle_update_plan(
        previous_items,
        [current_record],
        {
            source_id: {
                "index_observation_complete": bool(observation.get("index_observation_complete")),
                "reachable": observation.get("index_reachable", True),
                "checked_at": observed_at,
            }
        },
        lifecycle_state=state_document,
        existing_versions=deepcopy(observation.get("existing_versions") or []),
        existing_events=deepcopy(observation.get("existing_events") or []),
        run_id=run_id,
        observed_at=observed_at,
        long_absence_observation_threshold=int(
            policy.get("long_absence_observation_threshold", DEFAULT_LONG_ABSENCE_OBSERVATION_THRESHOLD)
        ),
        long_absence_min_days=int(policy.get("long_absence_min_days", DEFAULT_LONG_ABSENCE_MIN_DAYS)),
        detail_failure_attention_threshold=int(
            policy.get("detail_failure_attention_threshold", DEFAULT_DETAIL_FAILURE_ATTENTION_THRESHOLD)
        ),
        max_item_versions_per_record=int(
            policy.get("max_item_versions_per_record", DEFAULT_MAX_ITEM_VERSIONS_PER_RECORD)
        ),
        max_lifecycle_events=int(policy.get("max_lifecycle_events", DEFAULT_MAX_LIFECYCLE_EVENTS)),
    )
    record_id = str(current_record.get("id") or "")
    updated_item = next((item for item in plan.updated_items if str(item.get("id") or "") == record_id), None)
    return {
        "updated_item": updated_item,
        "updated_lifecycle_state": deepcopy(plan.updated_lifecycle_state.get("items", {}).get(record_id)),
        "new_versions": deepcopy(plan.new_versions),
        "new_events": deepcopy(plan.new_lifecycle_events),
        "warnings": deepcopy(plan.warnings),
        "ignored_as_stale": plan.ignored_as_stale,
        "duplicate_run": plan.duplicate_run,
    }


def validate_lifecycle_update_plan(plan: LifecycleUpdatePlan) -> None:
    state_items = plan.updated_lifecycle_state.get("items", {})
    if not isinstance(state_items, dict):
        raise ValueError("生命周期状态 items 必须是 object。")
    for record_id, state in state_items.items():
        if state.get("lifecycle_state") not in ALLOWED_LIFECYCLE_STATES:
            raise ValueError(f"记录 {record_id} 的 lifecycle_state 非法。")
        if int(state.get("semantic_version") or 0) < 1 or int(state.get("extraction_revision") or 0) < 1:
            raise ValueError(f"记录 {record_id} 的版本号非法。")
    version_ids = [str(item.get("version_id") or "") for item in plan.all_versions]
    event_ids = [str(item.get("event_id") or "") for item in plan.all_lifecycle_events]
    if len(version_ids) != len(set(version_ids)) or any(not item for item in version_ids):
        raise ValueError("item_versions.jsonl 存在重复或空 version_id。")
    if len(event_ids) != len(set(event_ids)) or any(not item for item in event_ids):
        raise ValueError("lifecycle_events.jsonl 存在重复或空 event_id。")
    if any(item.get("version_kind") not in ALLOWED_VERSION_KINDS for item in plan.all_versions):
        raise ValueError("item_versions.jsonl 包含非法 version_kind。")
    if any(item.get("event_type") not in ALLOWED_EVENT_TYPES for item in plan.all_lifecycle_events):
        raise ValueError("lifecycle_events.jsonl 包含非法 event_type。")
    if plan.lifecycle_report.get("run_id") != plan.updated_lifecycle_state.get("run_id"):
        raise ValueError("生命周期关键文件 run_id 不一致。")


def _json_text(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _jsonl_text(records: Iterable[dict[str, Any]]) -> str:
    return "".join(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n" for record in records)


def write_lifecycle_transaction(
    plan: LifecycleUpdatePlan,
    *,
    items_path: Path = ITEMS_FILE,
    lifecycle_state_path: Path = ITEM_LIFECYCLE_STATE_FILE,
    versions_path: Path = ITEM_VERSIONS_FILE,
    events_path: Path = LIFECYCLE_EVENTS_FILE,
    report_path: Path = LIFECYCLE_REPORT_FILE,
) -> None:
    validate_lifecycle_update_plan(plan)
    payloads = {
        items_path: _jsonl_text(plan.updated_items),
        lifecycle_state_path: _json_text(plan.updated_lifecycle_state),
        versions_path: _jsonl_text(plan.all_versions),
        events_path: _jsonl_text(plan.all_lifecycle_events),
        report_path: _json_text(plan.lifecycle_report),
    }
    temporary_paths: dict[Path, Path] = {}
    backup_paths: dict[Path, Path] = {}
    replaced: list[Path] = []
    try:
        for path, content in payloads.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(path.suffix + ".phase4d.tmp")
            temporary.write_text(content, encoding="utf-8", newline="\n")
            temporary_paths[path] = temporary
        for path in payloads:
            if path.exists():
                backup = path.with_suffix(path.suffix + ".phase4d.bak")
                shutil.copy2(path, backup)
                backup_paths[path] = backup
        for path, temporary in temporary_paths.items():
            os.replace(temporary, path)
            replaced.append(path)
    except Exception:
        for path in reversed(replaced):
            backup = backup_paths.get(path)
            if backup and backup.exists():
                os.replace(backup, path)
            elif path.exists():
                path.unlink()
        raise
    finally:
        for temporary in temporary_paths.values():
            if temporary.exists():
                temporary.unlink()
        for backup in backup_paths.values():
            if backup.exists():
                backup.unlink()
