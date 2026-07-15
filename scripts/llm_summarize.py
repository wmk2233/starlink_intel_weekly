from __future__ import annotations

import argparse
import copy
import json
import os
import re
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
ITEMS_FILE = DATA_DIR / "items.jsonl"
SOURCE_STATUS_FILE = DATA_DIR / "source_status.json"
EXTRACTION_QUALITY_FILE = DATA_DIR / "extraction_quality.json"
WEEKLY_MANIFEST_FILE = DATA_DIR / "weekly_manifest.json"
LLM_SUMMARY_FILE = DATA_DIR / "llm_summaries.json"
LLM_AUDIT_FILE = DATA_DIR / "llm_audit.json"
LLM_USAGE_FILE = DATA_DIR / "llm_usage.jsonl"
DEFAULT_PROVIDER = "deepseek"
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
DEFAULT_DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEFAULT_DEEPSEEK_MODEL = "deepseek-v4-flash"
SUPPORTED_PROVIDERS = {"openai", "deepseek"}
LEGACY_DEEPSEEK_MODELS = {"deepseek-chat", "deepseek-reasoner"}
SUMMARY_VERSION = "llm_reference_aligned_v2"
DEDUP_STRATEGY = "source_id+normalized_url_latest_record"
DEFAULT_MAX_USAGE_RECORDS = 200
TRACKING_QUERY_PARAMETERS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "fbclid",
    "gclid",
}
TIMESTAMP_FIELDS = [
    "last_seen_at",
    "updated_at",
    "fetched_at",
    "collected_at",
    "generated_at",
    "first_seen_at",
    "detail_fetch_status",
    "last_detail_attempt_at",
    "last_detail_success_at",
    "last_detail_error_type",
    "current_run_data_reused",
    "detail_parse_method",
    "semantic_content_hash",
    "extraction_change_status",
    "change_reason",
]

ALLOWED_ITEM_FIELDS = [
    "id",
    "source_id",
    "source_name",
    "source_type",
    "reliability_tier",
    "category",
    "record_type",
    "record_scope",
    "title",
    "url",
    "canonical_url",
    "published_at",
    "published_date_text",
    "summary",
    "evidence",
    "change_status",
    "extraction_change_status",
    "lifecycle_state",
    "current_run_data_reused",
    "lifecycle_events_this_run",
    "semantic_change_evidence",
    "attention_required",
    "extracted_level",
    "source_quality",
    "extraction_confidence",
    "matched_keywords",
    "candidate_links",
    "extraction_notes",
    "field_evidence",
    "structured_fields",
    "is_starlink_related",
    "relevance_reason",
    "starlink_relevance",
    "seen_in_current_index",
    "last_seen_at",
    "updated_at",
    "fetched_at",
    "collected_at",
    "generated_at",
    "first_seen_at",
]

PLACEHOLDER_API_KEYS = {
    "",
    "your_openai_api_key_here",
    "your_deepseek_api_key_here",
}
FACT_EXPANSION_PHRASES = [
    "发射成功",
    "计划发射",
    "任务完成",
    "载荷数量",
    "覆盖范围扩大",
    "服务开通",
    "技术升级",
    "网络容量提升",
    "速率提升",
    "用户增长",
    "终端升级",
    "直连手机已部署",
]
URL_PATTERN = re.compile(r"https?://[^\s\"'<>]+")


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def current_week_id() -> str:
    iso = datetime.now().astimezone().isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def is_truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def is_api_key_configured(value: str | None) -> bool:
    return str(value or "").strip() not in PLACEHOLDER_API_KEYS


def load_project_env() -> None:
    if os.getenv("PYTHON_DOTENV_DISABLED") != "1":
        load_dotenv(PROJECT_ROOT / ".env", override=False)


def project_path(path_value: str | Path) -> Path:
    path = Path(path_value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def read_items_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as file:
        for line in file:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                value = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                records.append(value)
    return records


def normalize_source_url(url: str) -> str:
    raw = str(url or "").strip()
    if not raw:
        return ""
    try:
        parts = urlsplit(raw)
        if not parts.scheme or not parts.hostname:
            return raw
        scheme = parts.scheme.lower()
        hostname = parts.hostname.lower()
        port = parts.port
        if ":" in hostname and not hostname.startswith("["):
            hostname = f"[{hostname}]"
        netloc = hostname
        if parts.username:
            credentials = parts.username
            if parts.password:
                credentials += f":{parts.password}"
            netloc = f"{credentials}@{netloc}"
        if port is not None:
            netloc = f"{netloc}:{port}"
        path = parts.path or ""
        if path and path != "/":
            path = path.rstrip("/")
        query_items = [
            (key, value)
            for key, value in parse_qsl(parts.query, keep_blank_values=True)
            if key.lower() not in TRACKING_QUERY_PARAMETERS
        ]
        query_items.sort(key=lambda item: (item[0], item[1]))
        return urlunsplit((scheme, netloc, path, urlencode(query_items, doseq=True), ""))
    except (TypeError, ValueError):
        return raw


def build_allowed_reference_pairs(records: list[dict[str, Any]]) -> list[dict[str, str]]:
    pairs: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for record in records:
        record_id = str(record.get("id") or "").strip()
        canonical_url = normalize_source_url(
            str(record.get("canonical_url") or record.get("url") or "")
        )
        pair = (record_id, canonical_url)
        if not record_id or not canonical_url or pair in seen:
            continue
        seen.add(pair)
        pairs.append({"record_id": record_id, "canonical_url": canonical_url})
    return pairs


def empty_reference_alignment_stats(status: str = "not_run") -> dict[str, int | str]:
    return {
        "output_record_references_before_dedup": 0,
        "output_record_references_after_dedup": 0,
        "output_url_references_before_dedup": 0,
        "output_url_references_after_dedup": 0,
        "invalid_record_ids_removed": 0,
        "invalid_urls_removed": 0,
        "missing_record_ids_repaired": 0,
        "missing_urls_repaired": 0,
        "mismatched_reference_pairs_removed": 0,
        "key_points_removed_without_sources": 0,
        "source_based_notes_removed": 0,
        "reference_alignment_status": status,
    }


def parse_record_timestamp(record: dict[str, Any]) -> datetime | None:
    for field in TIMESTAMP_FIELDS:
        value = record.get(field)
        if not value:
            continue
        text = str(value).strip()
        if not text:
            continue
        try:
            if text.endswith(("Z", "z")):
                text = text[:-1] + "+00:00"
            parsed = datetime.fromisoformat(text)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed
        except (TypeError, ValueError):
            continue
    return None


def _timestamp_value(record: dict[str, Any]) -> float:
    parsed = parse_record_timestamp(record)
    return parsed.timestamp() if parsed is not None else float("-inf")


def _record_completeness(record: dict[str, Any]) -> int:
    return sum(value not in (None, "", [], {}) for value in record.values())


def _dedup_source_identity(record: dict[str, Any], normalized_url: str) -> str:
    for field in ["source_id", "source_name"]:
        value = str(record.get(field) or "").strip()
        if value:
            return value.lower()
    try:
        hostname = urlsplit(normalized_url).hostname
    except ValueError:
        hostname = None
    return str(hostname or "unknown_source").lower()


def deduplicate_llm_input_records(records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    groups: dict[tuple[str, str], list[tuple[int, dict[str, Any]]]] = {}
    group_order: list[tuple[str, str]] = []
    for index, original in enumerate(records):
        record = copy.deepcopy(original)
        normalized_url = normalize_source_url(str(record.get("url") or ""))
        source_identity = _dedup_source_identity(record, normalized_url)
        key = (source_identity, normalized_url)
        if key not in groups:
            groups[key] = []
            group_order.append(key)
        groups[key].append((index, record))

    selected: list[dict[str, Any]] = []
    for key in group_order:
        candidates = groups[key]
        selected_index, selected_record = max(
            candidates,
            key=lambda item: (_timestamp_value(item[1]), item[0]),
        )
        merged = copy.deepcopy(selected_record)
        for _index, candidate in sorted(
            candidates,
            key=lambda item: (_record_completeness(item[1]), item[0]),
            reverse=True,
        ):
            for field, value in candidate.items():
                if merged.get(field) in (None, "", [], {}) and value not in (None, "", [], {}):
                    merged[field] = copy.deepcopy(value)
        merged["url"] = normalize_source_url(str(merged.get("url") or ""))
        merged["_dedup_selected_input_index"] = selected_index
        selected.append(merged)

    stats = {
        "input_records_before_dedup": len(records),
        "input_records_after_dedup": len(selected),
        "duplicate_records_removed": max(0, len(records) - len(selected)),
        "dedup_strategy": DEDUP_STRATEGY,
    }
    return selected, stats


def truncate_text(value: object, max_length: int) -> str:
    text = "" if value is None else str(value)
    text = text.replace("\r", " ").replace("\n", " ").strip()
    if len(text) <= max_length:
        return text
    return text[: max_length - 1].rstrip() + "…"


def normalize_candidate_links(value: object) -> list[object]:
    if not isinstance(value, list):
        return []
    normalized: list[object] = []
    for item in value[:5]:
        if isinstance(item, str):
            normalized.append(item)
        elif isinstance(item, dict):
            normalized.append({key: item.get(key) for key in ["title", "url"] if item.get(key)})
    return normalized


def normalize_item(item: dict[str, Any]) -> dict[str, Any]:
    normalized = {field: item.get(field) for field in ALLOWED_ITEM_FIELDS}
    normalized["evidence"] = truncate_text(normalized.get("evidence"), 800)
    normalized["candidate_links"] = normalize_candidate_links(normalized.get("candidate_links"))
    if not isinstance(normalized.get("matched_keywords"), list):
        normalized["matched_keywords"] = []
    if not isinstance(normalized.get("lifecycle_events_this_run"), list):
        normalized["lifecycle_events_this_run"] = []
    if not isinstance(normalized.get("semantic_change_evidence"), dict):
        normalized["semantic_change_evidence"] = {}
    return normalized


def select_items(
    items: list[dict[str, Any]],
    max_items: int,
    source_status: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    source_statuses = (source_status or {}).get("sources", {})
    current_items = [item for item in items if item.get("seen_in_current_index") is not False]
    sources_with_item_level = {
        str(item.get("source_id") or "")
        for item in current_items
        if item.get("record_scope") == "item" or item.get("extracted_level") == "item_level"
    }
    preferred: list[dict[str, Any]] = []
    for item in current_items:
        source_id = str(item.get("source_id") or "")
        is_item = item.get("record_scope") == "item" or item.get("extracted_level") == "item_level"
        if source_id in sources_with_item_level and not is_item:
            continue
        if source_id == "spacex_official_launches" and is_item and item.get("starlink_relevance") != "direct":
            continue
        preferred.append(item)

    def priority(item: dict[str, Any]) -> int:
        item_status = str(item.get("change_status") or "").lower()
        if item_status == "new":
            return 0
        if item_status == "changed":
            return 1
        lifecycle_events = set(str(value) for value in item.get("lifecycle_events_this_run", []) if value)
        if "detail_fetch_recovered" in lifecycle_events:
            return 2
        if "reappeared" in lifecycle_events:
            return 3
        if item.get("attention_required") is True:
            return 4
        if item_status == "baseline":
            return 5
        source_id = str(item.get("source_id") or "")
        page_status = source_statuses.get(source_id, {}) if isinstance(source_statuses, dict) else {}
        if item_status == "unchanged" and str(page_status.get("change_status") or "").lower() == "changed":
            return 6
        if item_status == "unchanged":
            return 7
        return 8

    sorted_items = sorted(
        preferred,
        key=lambda item: (
            priority(item),
            -_timestamp_value(item),
            -int(item.get("_dedup_selected_input_index") or 0),
        ),
    )
    return [normalize_item(item) for item in sorted_items[:max_items]]


def build_monitoring_context(
    source_status: dict[str, Any],
    extraction_quality: dict[str, Any],
    selected_records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    statuses = source_status.get("sources", {}) if isinstance(source_status, dict) else {}
    qualities = extraction_quality.get("sources", {}) if isinstance(extraction_quality, dict) else {}
    statuses = statuses if isinstance(statuses, dict) else {}
    qualities = qualities if isinstance(qualities, dict) else {}
    record_sources = {
        str(record.get("source_id") or "")
        for record in selected_records
        if str(record.get("source_id") or "")
    }
    source_ids = list(dict.fromkeys([*statuses.keys(), *qualities.keys(), *sorted(record_sources)]))
    contexts: list[dict[str, Any]] = []
    for source_id in source_ids:
        status = statuses.get(source_id, {}) if isinstance(statuses.get(source_id, {}), dict) else {}
        quality = qualities.get(source_id, {}) if isinstance(qualities.get(source_id, {}), dict) else {}
        source_records = [record for record in selected_records if str(record.get("source_id") or "") == source_id]
        fallback = source_records[0] if source_records else {}
        new_items = int(status.get("new_items") or 0)
        changed_items = int(status.get("changed_items") or 0)
        unchanged_items = int(status.get("unchanged_items") or 0)
        baseline_items = int(status.get("baseline_items") or 0)
        page_change_status = str(status.get("change_status") or quality.get("change_status") or "unknown")
        if new_items > 0 or changed_items > 0:
            interpretation = "当前规则检测到新增或内容变化条目，仍需结合来源链接人工复核。"
        elif baseline_items > 0:
            interpretation = "首次成功条目抽取已建立 baseline；这些历史条目不属于本周新增。"
        elif page_change_status == "changed":
            interpretation = "页面级 hash 发生变化，但当前规则未检测到可确认的新增或内容变化条目。"
        elif page_change_status == "unchanged":
            interpretation = "页面级 hash 未发生变化，当前规则也未检测到新增或内容变化条目。"
        else:
            interpretation = "页面级变化状态暂不明确，当前规则未检测到可确认的新增或内容变化条目。"
        contexts.append(
            {
                "source_id": source_id,
                "source_name": str(status.get("source_name") or quality.get("source_name") or fallback.get("source_name") or source_id),
                "page_status": str(status.get("health_status") or quality.get("health_status") or "unknown"),
                "page_change_status": page_change_status,
                "new_items": new_items,
                "changed_items": changed_items,
                "baseline_items": baseline_items,
                "unchanged_items": unchanged_items,
                "extracted_level": str(
                    status.get("dominant_extracted_level")
                    or quality.get("dominant_extracted_level")
                    or fallback.get("extracted_level")
                    or "unknown"
                ),
                "source_quality": str(
                    status.get("dominant_source_quality")
                    or quality.get("dominant_source_quality")
                    or fallback.get("source_quality")
                    or "unknown"
                ),
                "interpretation": interpretation,
            }
        )
    return contexts


def build_guardrails(strict_source: bool) -> dict[str, bool]:
    return {
        "strict_source": strict_source,
        "no_external_knowledge": True,
        "no_unsourced_claims": True,
        "page_level_no_fact_expansion": True,
        "monitoring_context_model_generated": False,
        "source_based_notes_model_generated": False,
        "paired_references_required": True,
    }


def build_audit(
    *,
    enabled: bool,
    provider: str,
    status: str,
    reason: str,
    model: str | None,
    base_url_label: str,
    input_records: int,
    summary_generated: bool,
    validation_status: str,
    strict_source: bool,
    errors: list[str] | None = None,
    warnings: list[str] | None = None,
    dedup_stats: dict[str, Any] | None = None,
    output_reference_stats: dict[str, Any] | None = None,
    usage: dict[str, int | float | None] | None = None,
    monitoring_context: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    dedup = dedup_stats or {
        "input_records_before_dedup": input_records,
        "input_records_after_dedup": input_records,
        "duplicate_records_removed": 0,
        "dedup_strategy": DEDUP_STRATEGY,
    }
    dedup.setdefault("raw_candidate_records", dedup.get("input_records_before_dedup", input_records))
    dedup.setdefault("records_after_url_dedup", dedup.get("input_records_after_dedup", input_records))
    dedup.setdefault("final_core_input_records", input_records)
    dedup.setdefault("final_core_unique_urls", input_records)
    dedup.setdefault("reused_historical_records", 0)
    references = empty_reference_alignment_stats()
    if output_reference_stats:
        references.update(output_reference_stats)
    usage_data = empty_usage()
    if usage:
        usage_data.update({key: usage.get(key) for key in usage_data})
    api_called = status in {"generated", "validation_failed", "api_error"}
    error_type: str | None = None
    if status == "sdk_missing":
        error_type = "ImportError"
    elif status == "api_error" and errors:
        error_type = str(errors[0])
    elif status == "validation_failed":
        error_type = "validation_failed"
    elif status == "skipped_invalid_provider":
        error_type = "invalid_provider"
    return {
        "generated_at": now_iso(),
        "llm_enabled": enabled,
        "llm_provider": provider,
        "llm_status": status,
        "api_called": api_called,
        "error_type": error_type,
        "model": model,
        "base_url_label": base_url_label,
        "reason": reason,
        "summary_generated": summary_generated,
        "input_records": input_records,
        **dedup,
        "unique_source_urls": dedup.get("unique_source_urls", input_records),
        **references,
        "usage": usage_data,
        "monitoring_context": monitoring_context or [],
        "validation_status": validation_status,
        "errors": errors or [],
        "warnings": warnings or [],
        "guardrails": build_guardrails(strict_source),
    }


def write_json(path: Path, payload: dict[str, Any], dry_run: bool) -> None:
    if dry_run:
        print(f"[dry-run] 不会写入：{path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def write_json_atomic(path: Path, payload: dict[str, Any], dry_run: bool) -> None:
    if dry_run:
        print(f"[dry-run] 不会原子写入：{path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as file:
            file.write(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
        os.replace(temporary_path, path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def empty_usage() -> dict[str, int | float | None]:
    return {
        "prompt_tokens": None,
        "completion_tokens": None,
        "total_tokens": None,
        "latency_ms": None,
    }


def _usage_value(usage: object, *names: str) -> int | None:
    for name in names:
        value = usage.get(name) if isinstance(usage, dict) else getattr(usage, name, None)
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)) and value >= 0:
            return int(value)
    return None


def extract_response_usage(response: Any) -> dict[str, int | float | None]:
    usage = getattr(response, "usage", None)
    if usage is None and isinstance(response, dict):
        usage = response.get("usage")
    prompt_tokens = _usage_value(usage, "prompt_tokens", "input_tokens")
    completion_tokens = _usage_value(usage, "completion_tokens", "output_tokens")
    total_tokens = _usage_value(usage, "total_tokens")
    if total_tokens is None and prompt_tokens is not None and completion_tokens is not None:
        total_tokens = prompt_tokens + completion_tokens
    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "latency_ms": None,
    }


def build_usage_record(audit: dict[str, Any]) -> dict[str, Any]:
    usage = audit.get("usage", {}) if isinstance(audit.get("usage"), dict) else {}
    return {
        "generated_at": now_iso(),
        "week_id": current_week_id(),
        "llm_enabled": audit.get("llm_enabled"),
        "api_called": audit.get("api_called", False),
        "provider": audit.get("llm_provider"),
        "model": audit.get("model"),
        "status": audit.get("llm_status"),
        "validation_status": audit.get("validation_status"),
        "input_records_before_dedup": audit.get("input_records_before_dedup"),
        "input_records_after_dedup": audit.get("input_records_after_dedup"),
        "duplicate_records_removed": audit.get("duplicate_records_removed"),
        "unique_source_urls": audit.get("unique_source_urls"),
        "raw_candidate_records": audit.get("raw_candidate_records"),
        "records_after_url_dedup": audit.get("records_after_url_dedup"),
        "final_core_input_records": audit.get("final_core_input_records"),
        "final_core_unique_urls": audit.get("final_core_unique_urls"),
        "reused_historical_records": audit.get("reused_historical_records"),
        "invalid_record_ids_removed": audit.get("invalid_record_ids_removed"),
        "invalid_urls_removed": audit.get("invalid_urls_removed"),
        "missing_record_ids_repaired": audit.get("missing_record_ids_repaired"),
        "missing_urls_repaired": audit.get("missing_urls_repaired"),
        "key_points_removed_without_sources": audit.get("key_points_removed_without_sources"),
        "reference_alignment_status": audit.get("reference_alignment_status"),
        "prompt_tokens": usage.get("prompt_tokens"),
        "completion_tokens": usage.get("completion_tokens"),
        "total_tokens": usage.get("total_tokens"),
        "latency_ms": usage.get("latency_ms"),
        "error_type": audit.get("error_type"),
    }


def append_usage_record(path: Path, audit: dict[str, Any], max_records: int, dry_run: bool) -> None:
    if dry_run:
        print(f"[dry-run] 不会追加 LLM 用量记录：{path}")
        return
    existing: list[dict[str, Any]] = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                existing.append(value)
    existing.append(build_usage_record(audit))
    existing = existing[-max_records:]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n" for record in existing),
        encoding="utf-8",
        newline="\n",
    )


def persist_audit_and_usage(
    audit_path: Path,
    usage_path: Path,
    audit: dict[str, Any],
    max_usage_records: int,
    dry_run: bool,
) -> None:
    write_json(audit_path, audit, dry_run)
    append_usage_record(usage_path, audit, max_usage_records, dry_run)


def system_prompt() -> str:
    return (
        "你是一个来源约束型情报摘要助手。\n"
        "你只能根据输入 JSON 中的字段生成摘要。\n"
        "不得使用外部知识。\n"
        "不得使用模型记忆。\n"
        "不得推测未给出的事实。\n"
        "不得编造发射时间、任务状态、载荷数量、技术细节、商业服务状态。\n"
        "页面可达性、页面 hash、页面变化状态和条目计数由代码确定性生成，不属于你的输出范围。\n"
        "不得生成 source_based_notes，也不得引用索引页或 monitoring context URL。\n"
        "baseline 只用于兼容旧阶段；已有历史记录且本轮无变化时，禁止写成本周新增。\n"
        "同一来源存在 item_level 时，应以条目级记录为核心，不得把 page_level 当作核心事实。\n"
        "SpaceX 条目只有 starlink_relevance=direct 时才能进入 Starlink 核心结论。\n"
        "如果 current_run_data_reused=true，本轮未重新确认详情正文。只能说明该记录来自最近一次成功解析，"
        "不得描述为本轮新确认内容。\n"
        "change_status=new 表示系统本轮首次发现该 URL，不一定表示官方本周发布；只有输入中存在明确官方发布日期证据时才能写本周发布。\n"
        "change_status=changed 仅表示本轮检测到结构化官方内容变化。\n"
        "extraction_change_status=improved 只表示解析完整度提升，不代表官方事实变化，也不得写成内容更新。\n"
        "lifecycle_state=temporarily_missing 表示成功解析索引时未发现历史条目，不代表官方删除。\n"
        "lifecycle_state=long_absent 表示连续多次未在索引中发现，不代表官方删除或下线。\n"
        "detail_fetch_failed 表示采集器未成功解析详情，不代表官方页面或业务故障。\n"
        "detail_fetch_recovered 表示采集链路恢复，不代表官方服务恢复。\n"
        "reappeared 表示历史条目重新出现在索引中，不代表重新发布。\n"
        "不得将 parser enrichment 或字段补全描述为官方内容更新。\n"
        "如果没有 new 或 changed 条目，必须明确写“本周未检测到新增或内容变化条目”。\n"
        "每个 key point 必须逐字使用 allowed_reference_pairs 中属于同一记录的 record_id 和 canonical_url。\n"
        "不得使用相对 URL、改写 URL、索引页 URL 或外部 URL。\n"
        "只生成 overall_summary 和 key_points。\n"
        "输出必须是合法 JSON。"
    )


def build_user_prompt(
    selected_items: list[dict[str, Any]],
    source_status: dict[str, Any] | None = None,
    extraction_quality: dict[str, Any] | None = None,
    weekly_manifest: dict[str, Any] | None = None,
    monitoring_context: list[dict[str, Any]] | None = None,
) -> str:
    del source_status, extraction_quality, weekly_manifest, monitoring_context
    allowed_pairs = build_allowed_reference_pairs(selected_items)
    pair_by_id = {pair["record_id"]: pair["canonical_url"] for pair in allowed_pairs}
    final_core_records: list[dict[str, Any]] = []
    for item in selected_items:
        record_id = str(item.get("id") or "").strip()
        if record_id not in pair_by_id:
            continue
        record = copy.deepcopy(item)
        record.pop("candidate_links", None)
        record["url"] = pair_by_id[record_id]
        record["canonical_url"] = pair_by_id[record_id]
        final_core_records.append(record)
    payload = {
        "instructions": {
            "output_json_schema": {
                "overall_summary": "string",
                "key_points": [
                    {
                        "point": "string",
                        "source_record_ids": ["record id"],
                        "source_urls": ["url"],
                        "caveat": "string",
                    }
                ],
            },
            "format": "只输出 JSON，不要 Markdown，不要代码块。",
            "reference_rules": [
                "逐字使用 allowed_reference_pairs 中的 record_id 和 canonical_url。",
                "record_id 与 canonical_url 必须来自同一个允许引用对。",
                "不得输出索引页 URL、相对 URL、改写 URL 或外部 URL。",
                "不得生成 source_based_notes；页面监测解释由代码生成。",
            ],
        },
        "source_constraints": {
            "no_external_sources": True,
            "baseline_is_not_new": True,
            "item_level_preferred": True,
            "spacex_core_requires_direct_starlink_relevance": True,
            "reused_history_is_not_current_confirmation": True,
            "new_is_first_observed_not_weekly_publication": True,
            "semantic_change_is_distinct_from_extraction_improvement": True,
            "missing_is_not_deletion": True,
            "fetch_failure_is_not_official_failure": True,
            "collector_recovery_is_not_service_recovery": True,
            "reappeared_is_not_republication": True,
            "monitoring_context_is_not_model_input": True,
        },
        "allowed_reference_pairs": allowed_pairs,
        "final_core_records": final_core_records,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)


def output_text_from_response(response: Any) -> str:
    direct_text = getattr(response, "output_text", None)
    if isinstance(direct_text, str) and direct_text.strip():
        return direct_text.strip()
    try:
        output = getattr(response, "output", [])
        parts: list[str] = []
        for item in output:
            for content in getattr(item, "content", []) or []:
                text = getattr(content, "text", None)
                if text:
                    parts.append(str(text))
        if parts:
            return "\n".join(parts).strip()
    except Exception:
        return ""
    return ""


def call_openai(model: str, api_key: str, prompt: str) -> tuple[str, dict[str, int | float | None]]:
    from openai import OpenAI

    client = OpenAI(api_key=api_key)
    if hasattr(client, "responses"):
        response = client.responses.create(
            model=model,
            instructions=system_prompt(),
            input=prompt,
            max_output_tokens=1200,
        )
        return output_text_from_response(response), extract_response_usage(response)

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt()},
            {"role": "user", "content": prompt},
        ],
        response_format={"type": "json_object"},
    )
    return str(response.choices[0].message.content or "").strip(), extract_response_usage(response)


def call_deepseek(
    model: str,
    api_key: str,
    base_url: str,
    prompt: str,
) -> tuple[str, dict[str, int | float | None]]:
    from openai import OpenAI

    client = OpenAI(api_key=api_key, base_url=base_url)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt()},
            {"role": "user", "content": prompt},
        ],
        stream=False,
        response_format={"type": "json_object"},
    )
    return str(response.choices[0].message.content or "").strip(), extract_response_usage(response)


def narrative_text(summary: dict[str, Any]) -> str:
    parts = [str(summary.get("overall_summary") or "")]
    for point in summary.get("key_points", []) if isinstance(summary.get("key_points"), list) else []:
        if isinstance(point, dict):
            parts.append(str(point.get("point") or ""))
            parts.append(str(point.get("caveat") or ""))
    return "\n".join(parts)


def extract_urls(value: object) -> set[str]:
    serialized = json.dumps(value, ensure_ascii=False, sort_keys=True)
    return set(URL_PATTERN.findall(serialized))


def _ordered_unique(values: object, normalizer: Any = str) -> list[str]:
    if not isinstance(values, list):
        return []
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value in (None, ""):
            continue
        normalized = normalizer(value)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


def align_llm_references(
    llm_output: dict[str, Any],
    allowed_records: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, int | str]]:
    allowed_pairs = build_allowed_reference_pairs(allowed_records)
    id_to_url = {pair["record_id"]: pair["canonical_url"] for pair in allowed_pairs}
    url_to_id = {pair["canonical_url"]: pair["record_id"] for pair in allowed_pairs}
    stats = empty_reference_alignment_stats()
    aligned = {
        "llm_summary_version": SUMMARY_VERSION,
        "overall_summary": llm_output.get("overall_summary", llm_output.get("overall_summary_cn")),
        "key_points": [],
    }
    changed = "overall_summary_cn" in llm_output or any(
        key not in {"overall_summary", "overall_summary_cn", "key_points"}
        for key in llm_output
    )

    source_notes = llm_output.get("source_based_notes")
    if isinstance(source_notes, list):
        stats["source_based_notes_removed"] = len(source_notes)
        changed = changed or bool(source_notes)
        for note in source_notes:
            if not isinstance(note, dict):
                continue
            note_ids = note.get("source_record_ids", [])
            note_urls = note.get("source_urls", [])
            if isinstance(note_ids, list):
                valid_note_ids = [str(value).strip() for value in note_ids if value not in (None, "")]
                stats["output_record_references_before_dedup"] += len(valid_note_ids)
                stats["invalid_record_ids_removed"] += sum(value not in id_to_url for value in valid_note_ids)
            if isinstance(note_urls, list):
                valid_note_urls = [normalize_source_url(str(value)) for value in note_urls if value not in (None, "")]
                stats["output_url_references_before_dedup"] += len(valid_note_urls)
                stats["invalid_urls_removed"] += sum(value not in url_to_id for value in valid_note_urls)

    raw_key_points = llm_output.get("key_points")
    if not isinstance(raw_key_points, list):
        raw_key_points = []
    for point in raw_key_points:
        if not isinstance(point, dict):
            stats["key_points_removed_without_sources"] += 1
            changed = True
            continue
        raw_ids = point.get("source_record_ids", [])
        raw_urls = point.get("source_urls", [])
        ids = [str(value).strip() for value in raw_ids if value not in (None, "")] if isinstance(raw_ids, list) else []
        urls = [normalize_source_url(str(value)) for value in raw_urls if value not in (None, "")] if isinstance(raw_urls, list) else []
        stats["output_record_references_before_dedup"] += len(ids)
        stats["output_url_references_before_dedup"] += len(urls)

        pairs: list[tuple[str, str]] = []
        seen_pairs: set[tuple[str, str]] = set()
        for index in range(max(len(ids), len(urls))):
            record_id = ids[index] if index < len(ids) else ""
            canonical_url = urls[index] if index < len(urls) else ""
            id_valid = bool(record_id and record_id in id_to_url)
            url_valid = bool(canonical_url and canonical_url in url_to_id)
            if record_id and not id_valid:
                stats["invalid_record_ids_removed"] += 1
                changed = True
            if canonical_url and not url_valid:
                stats["invalid_urls_removed"] += 1
                changed = True

            if id_valid and url_valid:
                if id_to_url[record_id] != canonical_url:
                    stats["mismatched_reference_pairs_removed"] += 1
                    changed = True
                    continue
                pair = (record_id, canonical_url)
            elif id_valid:
                pair = (record_id, id_to_url[record_id])
                stats["missing_urls_repaired"] += 1
                changed = True
            elif url_valid:
                pair = (url_to_id[canonical_url], canonical_url)
                stats["missing_record_ids_repaired"] += 1
                changed = True
            else:
                continue
            if pair in seen_pairs:
                changed = True
                continue
            seen_pairs.add(pair)
            pairs.append(pair)

        if not pairs:
            stats["key_points_removed_without_sources"] += 1
            changed = True
            continue
        aligned_point = {
            "point": point.get("point"),
            "source_record_ids": [pair[0] for pair in pairs],
            "source_urls": [pair[1] for pair in pairs],
            "caveat": point.get("caveat", ""),
        }
        if set(point) - {"point", "source_record_ids", "source_urls", "caveat"}:
            changed = True
        aligned["key_points"].append(aligned_point)
        stats["output_record_references_after_dedup"] += len(pairs)
        stats["output_url_references_after_dedup"] += len(pairs)

    if allowed_pairs and not aligned["key_points"]:
        stats["reference_alignment_status"] = "failed"
    elif changed:
        stats["reference_alignment_status"] = "repaired"
    else:
        stats["reference_alignment_status"] = "passed"
    return aligned, stats


def normalize_and_deduplicate_llm_references(
    llm_output: dict[str, Any],
    allowed_records: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, int | str]]:
    return align_llm_references(llm_output, allowed_records)


def validate_llm_output(raw_text: str, input_records: list[dict[str, Any]]) -> tuple[bool, dict[str, Any] | None, list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    try:
        summary = json.loads(raw_text)
    except json.JSONDecodeError:
        return False, None, ["LLM 输出不是合法 JSON。"], warnings
    if not isinstance(summary, dict):
        return False, None, ["LLM 输出顶层不是 JSON object。"], warnings

    if summary.get("llm_summary_version") != SUMMARY_VERSION:
        errors.append("llm_summary_version 不符合要求。")
    for key in ["overall_summary", "key_points"]:
        if key not in summary:
            errors.append(f"缺少字段：{key}")

    unexpected_fields = set(summary) - {"llm_summary_version", "overall_summary", "key_points"}
    if unexpected_fields:
        errors.append("LLM 摘要包含 schema 外字段。")
    if "source_based_notes" in summary:
        errors.append("source_based_notes 不得由模型生成。")

    allowed_pairs = build_allowed_reference_pairs(input_records)
    valid_pair_set = {(pair["record_id"], pair["canonical_url"]) for pair in allowed_pairs}
    valid_ids = {pair["record_id"] for pair in allowed_pairs}
    valid_urls = {pair["canonical_url"] for pair in allowed_pairs}

    key_points = summary.get("key_points", [])
    if not isinstance(key_points, list):
        errors.append("key_points 不是列表。")
        key_points = []
    if input_records and not key_points:
        errors.append("key_points 没有可验证的来源要点。")
    for index, point in enumerate(key_points, start=1):
        if not isinstance(point, dict):
            errors.append(f"key_points[{index}] 不是 object。")
            continue
        unexpected_point_fields = set(point) - {"point", "source_record_ids", "source_urls", "caveat"}
        if unexpected_point_fields:
            errors.append(f"key_points[{index}] 包含 schema 外字段。")
        if not str(point.get("point") or "").strip():
            errors.append(f"key_points[{index}] 缺少 point 文本。")
        ids = [str(item) for item in point.get("source_record_ids", []) if item]
        urls = [str(item) for item in point.get("source_urls", []) if item]
        if not ids or not urls:
            errors.append(f"key_points[{index}] 缺少来源记录或 URL。")
        if any(item not in valid_ids for item in ids):
            errors.append(f"key_points[{index}] 出现输入外 record id。")
        normalized_urls = [normalize_source_url(item) for item in urls]
        if any(item not in valid_urls for item in normalized_urls):
            errors.append(f"key_points[{index}] 出现输入外 URL。")
        if len(ids) != len(set(ids)):
            errors.append(f"key_points[{index}] 出现重复 record id。")
        if len(normalized_urls) != len(set(normalized_urls)):
            errors.append(f"key_points[{index}] 出现重复 URL。")
        if len(ids) != len(normalized_urls):
            errors.append(f"key_points[{index}] 的 record id 与 URL 数量不一致。")
        elif any(pair not in valid_pair_set for pair in zip(ids, normalized_urls)):
            errors.append(f"key_points[{index}] 的 record id 与 URL 不属于同一允许记录。")

    unexpected_urls = sorted(
        url for url in extract_urls(summary) if normalize_source_url(url) not in valid_urls
    )
    if unexpected_urls:
        errors.append("LLM 输出包含输入记录之外的 URL。")

    generated_text = narrative_text(summary)
    if input_records and not any(str(item.get("change_status") or "").lower() in {"new", "changed"} for item in input_records):
        if "本周未检测到新增或内容变化条目" not in generated_text:
            errors.append("未检测到 new/changed 条目时，摘要未明确说明本周无新增或内容变化。")

    if input_records and all(
        str(item.get("extracted_level")) == "page_level" and str(item.get("source_quality")) == "low" for item in input_records
    ):
        for phrase in FACT_EXPANSION_PHRASES:
            if phrase in generated_text:
                errors.append(f"page_level / low 记录疑似被扩展成事实：{phrase}")

    new_without_date = any(
        str(item.get("change_status") or "").lower() == "new" and not item.get("published_at")
        for item in input_records
    )
    if new_without_date and any(phrase in generated_text for phrase in ["本周发布", "本周首次发布"]):
        errors.append("new 条目缺少明确发布日期证据，不得描述为本周发布。")
    improved_only = any(
        str(item.get("extraction_change_status") or "").lower() == "improved"
        and str(item.get("change_status") or "").lower() != "changed"
        for item in input_records
    )
    if improved_only and any(phrase in generated_text for phrase in ["官方内容更新", "内容发生更新"]):
        errors.append("解析质量提升不得描述为官方内容更新。")
    if any(str(item.get("lifecycle_state") or "") in {"temporarily_missing", "long_absent"} for item in input_records):
        if any(phrase in generated_text for phrase in ["官方删除", "已经删除", "已经下线"]):
            errors.append("暂时消失或长期未见不得描述为官方删除或下线。")
    all_events = {
        str(event)
        for item in input_records
        for event in item.get("lifecycle_events_this_run", [])
        if event
    }
    if "detail_fetch_failed" in all_events and any(phrase in generated_text for phrase in ["官方故障", "服务故障"]):
        errors.append("详情抓取失败不得描述为官方或业务故障。")
    if "detail_fetch_recovered" in all_events and any(phrase in generated_text for phrase in ["服务已恢复", "官方服务恢复"]):
        errors.append("采集恢复不得描述为官方服务恢复。")
    if "reappeared" in all_events and "重新发布" in generated_text:
        errors.append("重新出现不得描述为官方重新发布。")
    if any(item.get("current_run_data_reused") is True for item in input_records):
        if any(phrase in generated_text for phrase in ["本轮重新确认", "本轮确认"]):
            errors.append("复用历史成功记录不得描述为本轮重新确认。")

    return not errors, summary, errors, warnings


def run_llm_summary(
    *,
    enabled: bool,
    dry_run: bool,
    input_items: str | Path = ITEMS_FILE,
    source_status: str | Path = SOURCE_STATUS_FILE,
    extraction_quality: str | Path = EXTRACTION_QUALITY_FILE,
    output: str | Path = LLM_SUMMARY_FILE,
    audit_output: str | Path = LLM_AUDIT_FILE,
    usage_output: str | Path = LLM_USAGE_FILE,
    max_items: int = 10,
    max_usage_records: int = DEFAULT_MAX_USAGE_RECORDS,
    model: str | None = None,
    provider: str | None = None,
    deepseek_api_key_env: str = "DEEPSEEK_API_KEY",
    deepseek_base_url: str | None = None,
    deepseek_model: str | None = None,
    strict_source: bool = True,
    fail_on_llm_error: bool = False,
) -> tuple[int, dict[str, Any]]:
    selected_provider = (provider or os.getenv("LLM_PROVIDER") or DEFAULT_PROVIDER).strip().lower()
    output_path = project_path(output)
    audit_path = project_path(audit_output)
    usage_path = project_path(usage_output)

    config_warnings: list[str] = []
    if selected_provider == "deepseek":
        selected_model = (
            model
            or deepseek_model
            or os.getenv("DEEPSEEK_MODEL")
            or DEFAULT_DEEPSEEK_MODEL
        ).strip()
        selected_base_url = (
            deepseek_base_url
            or os.getenv("DEEPSEEK_BASE_URL")
            or DEFAULT_DEEPSEEK_BASE_URL
        ).strip()
        if selected_base_url.rstrip("/") == DEFAULT_DEEPSEEK_BASE_URL.rstrip("/"):
            base_url_label = "deepseek_default"
        else:
            base_url_label = "custom_base_url"
        api_key_env = deepseek_api_key_env.strip() or "DEEPSEEK_API_KEY"
        if selected_model in LEGACY_DEEPSEEK_MODELS:
            config_warnings.append(
                f"{selected_model} 是旧模型名，建议改为 deepseek-v4-flash 或 deepseek-v4-pro。"
            )
    elif selected_provider == "openai":
        selected_model = (model or os.getenv("OPENAI_MODEL") or DEFAULT_OPENAI_MODEL).strip()
        selected_base_url = None
        base_url_label = "openai_default"
        api_key_env = "OPENAI_API_KEY"
    else:
        audit = build_audit(
            enabled=enabled,
            provider=selected_provider or "unknown",
            status="skipped_invalid_provider",
            reason="Unsupported LLM provider.",
            model=model,
            base_url_label="not_applicable",
            input_records=0,
            summary_generated=False,
            validation_status="skipped",
            strict_source=strict_source,
            errors=["LLM provider 仅支持 openai 或 deepseek。"],
        )
        persist_audit_and_usage(audit_path, usage_path, audit, max_usage_records, dry_run)
        print(f"LLM Provider：{selected_provider or 'unknown'}")
        print("LLM 摘要状态：skipped_invalid_provider")
        return 0, audit

    items = read_items_jsonl(project_path(input_items))
    source_status_data = read_json(project_path(source_status))
    extraction_quality_data = read_json(project_path(extraction_quality))
    weekly_manifest_data = read_json(WEEKLY_MANIFEST_FILE)
    deduplicated_items, dedup_stats = deduplicate_llm_input_records(items)
    selected_items = select_items(deduplicated_items, max_items, source_status_data)
    dedup_stats["unique_source_urls"] = len(
        {normalize_source_url(str(item.get("url") or "")) for item in deduplicated_items if item.get("url")}
    )
    dedup_stats.update(
        {
            "raw_candidate_records": dedup_stats["input_records_before_dedup"],
            "records_after_url_dedup": dedup_stats["input_records_after_dedup"],
            "final_core_input_records": len(selected_items),
            "final_core_unique_urls": len(
                {
                    normalize_source_url(str(item.get("url") or ""))
                    for item in selected_items
                    if item.get("url")
                }
            ),
            "reused_historical_records": sum(
                bool(item.get("current_run_data_reused")) for item in selected_items
            ),
            "allowed_reference_pair_count": len(build_allowed_reference_pairs(selected_items)),
        }
    )
    monitoring_context = build_monitoring_context(
        source_status_data,
        extraction_quality_data,
        selected_items,
    )

    if not enabled:
        audit = build_audit(
            enabled=False,
            provider=selected_provider,
            status="skipped",
            reason="LLM is disabled.",
            model=selected_model,
            base_url_label=base_url_label,
            input_records=len(selected_items),
            summary_generated=False,
            validation_status="skipped",
            strict_source=strict_source,
            warnings=config_warnings,
            dedup_stats=dedup_stats,
            monitoring_context=monitoring_context,
        )
        persist_audit_and_usage(audit_path, usage_path, audit, max_usage_records, dry_run)
        print(f"LLM Provider：{selected_provider}")
        print(f"LLM 模型：{selected_model}")
        print("LLM 摘要状态：skipped")
        return 0, audit

    if dry_run:
        audit = build_audit(
            enabled=True,
            provider=selected_provider,
            status="dry_run",
            reason=f"Dry run requested; {selected_provider} API was not called.",
            model=selected_model,
            base_url_label=base_url_label,
            input_records=len(selected_items),
            summary_generated=False,
            validation_status="skipped",
            strict_source=strict_source,
            warnings=config_warnings,
            dedup_stats=dedup_stats,
            monitoring_context=monitoring_context,
        )
        print(f"[dry-run] 不会调用 {selected_provider} API，也不会写入 LLM 输出文件。")
        print(f"LLM Provider：{selected_provider}")
        print(f"LLM 模型：{selected_model}")
        print("LLM 摘要状态：dry_run")
        return 0, audit

    api_key = os.getenv(api_key_env)
    if not is_api_key_configured(api_key):
        audit = build_audit(
            enabled=True,
            provider=selected_provider,
            status="skipped_no_api_key",
            reason=f"{api_key_env} is not configured.",
            model=selected_model,
            base_url_label=base_url_label,
            input_records=len(selected_items),
            summary_generated=False,
            validation_status="skipped",
            strict_source=strict_source,
            warnings=config_warnings,
            dedup_stats=dedup_stats,
            monitoring_context=monitoring_context,
        )
        persist_audit_and_usage(audit_path, usage_path, audit, max_usage_records, dry_run)
        print(f"LLM Provider：{selected_provider}")
        print(f"LLM 模型：{selected_model}")
        print("LLM 摘要状态：skipped_no_api_key")
        return 0, audit

    prompt = build_user_prompt(selected_items)

    usage = empty_usage()
    started_at = time.perf_counter()
    try:
        if selected_provider == "deepseek":
            call_result = call_deepseek(selected_model, str(api_key), str(selected_base_url), prompt)
        else:
            call_result = call_openai(selected_model, str(api_key), prompt)
        if isinstance(call_result, tuple):
            raw_output, response_usage = call_result
        else:
            raw_output, response_usage = str(call_result), empty_usage()
        usage.update(response_usage)
        usage["latency_ms"] = round((time.perf_counter() - started_at) * 1000, 2)
    except ImportError:
        usage["latency_ms"] = round((time.perf_counter() - started_at) * 1000, 2)
        audit = build_audit(
            enabled=True,
            provider=selected_provider,
            status="sdk_missing",
            reason="OpenAI Python SDK is not installed.",
            model=selected_model,
            base_url_label=base_url_label,
            input_records=len(selected_items),
            summary_generated=False,
            validation_status="skipped",
            strict_source=strict_source,
            errors=["OpenAI Python SDK 缺失，请安装 requirements.txt。"],
            warnings=config_warnings,
            dedup_stats=dedup_stats,
            usage=usage,
            monitoring_context=monitoring_context,
        )
        persist_audit_and_usage(audit_path, usage_path, audit, max_usage_records, dry_run)
        print("LLM 摘要状态：sdk_missing")
        return (1 if fail_on_llm_error else 0), audit
    except Exception as exc:
        usage["latency_ms"] = round((time.perf_counter() - started_at) * 1000, 2)
        audit = build_audit(
            enabled=True,
            provider=selected_provider,
            status="api_error",
            reason=f"{selected_provider} API call failed.",
            model=selected_model,
            base_url_label=base_url_label,
            input_records=len(selected_items),
            summary_generated=False,
            validation_status="not_validated",
            strict_source=strict_source,
            errors=[exc.__class__.__name__],
            warnings=config_warnings,
            dedup_stats=dedup_stats,
            usage=usage,
            monitoring_context=monitoring_context,
        )
        persist_audit_and_usage(audit_path, usage_path, audit, max_usage_records, dry_run)
        print("LLM 摘要状态：api_error")
        return (1 if fail_on_llm_error else 0), audit

    output_reference_stats: dict[str, Any] = empty_reference_alignment_stats()
    try:
        raw_summary = json.loads(raw_output)
    except json.JSONDecodeError:
        raw_summary = None
    if isinstance(raw_summary, dict):
        normalized_output, output_reference_stats = align_llm_references(
            raw_summary,
            selected_items,
        )
        validation_input = json.dumps(normalized_output, ensure_ascii=False)
    else:
        output_reference_stats["reference_alignment_status"] = "failed"
        validation_input = raw_output
    valid, summary, errors, validation_warnings = validate_llm_output(validation_input, selected_items)
    warnings = config_warnings + validation_warnings
    if not valid or summary is None:
        audit = build_audit(
            enabled=True,
            provider=selected_provider,
            status="validation_failed",
            reason="LLM output failed source-guardrail validation.",
            model=selected_model,
            base_url_label=base_url_label,
            input_records=len(selected_items),
            summary_generated=False,
            validation_status="failed",
            strict_source=strict_source,
            errors=errors,
            warnings=warnings,
            dedup_stats=dedup_stats,
            output_reference_stats=output_reference_stats,
            usage=usage,
            monitoring_context=monitoring_context,
        )
        persist_audit_and_usage(audit_path, usage_path, audit, max_usage_records, dry_run)
        print("LLM 摘要状态：validation_failed")
        return (1 if fail_on_llm_error else 0), audit

    payload = {
        "generated_at": now_iso(),
        "llm_enabled": True,
        "llm_provider": selected_provider,
        "llm_status": "generated",
        "model": selected_model,
        "base_url_label": base_url_label,
        "input_records": len(selected_items),
        "input_records_before_dedup": dedup_stats["input_records_before_dedup"],
        "input_records_after_dedup": dedup_stats["input_records_after_dedup"],
        "unique_source_urls": dedup_stats["unique_source_urls"],
        "raw_candidate_records": dedup_stats["raw_candidate_records"],
        "records_after_url_dedup": dedup_stats["records_after_url_dedup"],
        "final_core_input_records": dedup_stats["final_core_input_records"],
        "final_core_unique_urls": dedup_stats["final_core_unique_urls"],
        "reused_historical_records": dedup_stats["reused_historical_records"],
        "allowed_reference_pairs": build_allowed_reference_pairs(selected_items),
        "summary": summary,
    }
    audit = build_audit(
        enabled=True,
        provider=selected_provider,
        status="generated",
        reason="LLM summary generated and validated.",
        model=selected_model,
        base_url_label=base_url_label,
        input_records=len(selected_items),
        summary_generated=True,
        validation_status="passed",
        strict_source=strict_source,
        warnings=warnings,
        dedup_stats=dedup_stats,
        output_reference_stats=output_reference_stats,
        usage=usage,
        monitoring_context=monitoring_context,
    )
    write_json_atomic(output_path, payload, dry_run)
    persist_audit_and_usage(audit_path, usage_path, audit, max_usage_records, dry_run)
    print("LLM 摘要状态：generated")
    return 0, audit


def main() -> int:
    load_project_env()
    parser = argparse.ArgumentParser(description="生成受来源约束的可选 LLM 摘要。")
    parser.add_argument(
        "--enabled",
        action="store_true",
        default=is_truthy(os.getenv("LLM_ENABLED")),
        help="显式启用 LLM 摘要。",
    )
    parser.add_argument("--dry-run", action="store_true", help="演练流程，不写文件、不调用任何 LLM API。")
    parser.add_argument("--input-items", default="data/items.jsonl")
    parser.add_argument("--source-status", default="data/source_status.json")
    parser.add_argument("--extraction-quality", default="data/extraction_quality.json")
    parser.add_argument("--output", default="data/llm_summaries.json")
    parser.add_argument("--audit-output", default="data/llm_audit.json")
    parser.add_argument("--usage-output", default="data/llm_usage.jsonl")
    parser.add_argument("--max-items", type=int, default=10)
    parser.add_argument(
        "--max-usage-records",
        type=int,
        default=int(os.getenv("LLM_MAX_USAGE_RECORDS") or DEFAULT_MAX_USAGE_RECORDS),
    )
    parser.add_argument("--model", default=None)
    parser.add_argument("--provider", default=os.getenv("LLM_PROVIDER") or DEFAULT_PROVIDER)
    parser.add_argument("--deepseek-api-key-env", default="DEEPSEEK_API_KEY")
    parser.add_argument("--deepseek-base-url", default=os.getenv("DEEPSEEK_BASE_URL") or DEFAULT_DEEPSEEK_BASE_URL)
    parser.add_argument("--deepseek-model", default=os.getenv("DEEPSEEK_MODEL") or DEFAULT_DEEPSEEK_MODEL)
    parser.add_argument("--strict-source", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--fail-on-llm-error", action="store_true")
    args = parser.parse_args()

    if args.max_items < 1:
        print("--max-items 必须是大于等于 1 的整数。")
        return 2
    if args.max_usage_records < 1:
        print("--max-usage-records 必须是大于等于 1 的整数。")
        return 2

    return_code, _audit = run_llm_summary(
        enabled=args.enabled,
        dry_run=args.dry_run,
        input_items=args.input_items,
        source_status=args.source_status,
        extraction_quality=args.extraction_quality,
        output=args.output,
        audit_output=args.audit_output,
        usage_output=args.usage_output,
        max_items=args.max_items,
        max_usage_records=args.max_usage_records,
        model=args.model,
        provider=args.provider,
        deepseek_api_key_env=args.deepseek_api_key_env,
        deepseek_base_url=args.deepseek_base_url,
        deepseek_model=args.deepseek_model,
        strict_source=args.strict_source,
        fail_on_llm_error=args.fail_on_llm_error,
    )
    return return_code


if __name__ == "__main__":
    sys.exit(main())
