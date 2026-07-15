from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from parsers.common import DETAIL_ERROR_TYPES


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WEEKLY_DIR = PROJECT_ROOT / "weekly"
DATA_DIR = PROJECT_ROOT / "data"


def current_week_id() -> str:
    now = datetime.now().astimezone()
    iso = now.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def valid_json_file(path: Path) -> tuple[bool, str | None]:
    if not path.exists():
        return False, "文件不存在"
    try:
        json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return False, f"JSON 解析失败：line {exc.lineno}"
    return True, None


def load_json_file(path: Path) -> tuple[bool, dict[str, Any], str | None]:
    if not path.exists():
        return False, {}, "文件不存在"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return False, {}, f"JSON 解析失败：line {exc.lineno}"
    if not isinstance(data, dict):
        return False, {}, "JSON 顶层不是 object"
    return True, data, None


def valid_jsonl_file(path: Path) -> tuple[bool, str | None]:
    if not path.exists():
        return False, "文件不存在"
    try:
        with path.open("r", encoding="utf-8") as file:
            for line_number, line in enumerate(file, start=1):
                stripped = line.strip()
                if not stripped:
                    continue
                json.loads(stripped)
    except json.JSONDecodeError as exc:
        return False, f"JSONL 第 {line_number} 行解析失败：{exc.msg}"
    return True, None


def load_jsonl_records(path: Path) -> tuple[bool, list[dict[str, Any]], str | None]:
    if not path.exists():
        return False, [], "文件不存在"
    records: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as file:
            for line_number, line in enumerate(file, start=1):
                if not line.strip():
                    continue
                value = json.loads(line)
                if not isinstance(value, dict):
                    return False, records, f"JSONL 第 {line_number} 行不是 object"
                records.append(value)
    except json.JSONDecodeError as exc:
        return False, records, f"JSONL 第 {line_number} 行解析失败：{exc.msg}"
    return True, records, None


def add_check(report: dict[str, Any], name: str, passed: bool, error: str | None = None) -> None:
    report["checks"][name] = passed
    if not passed:
        report["errors"].append(f"{name}: {error or '检查失败'}")


def build_report(week_id: str) -> dict[str, Any]:
    summary_path = WEEKLY_DIR / f"{week_id}-summary.md"
    details_path = WEEKLY_DIR / f"{week_id}-details.md"
    index_path = WEEKLY_DIR / f"{week_id}.md"
    weekly_index_path = WEEKLY_DIR / "index.md"

    items_path = DATA_DIR / "items.jsonl"
    source_status_path = DATA_DIR / "source_status.json"
    extraction_quality_path = DATA_DIR / "extraction_quality.json"
    item_state_path = DATA_DIR / "item_extraction_state.json"
    item_report_path = DATA_DIR / "item_extraction_report.json"
    detail_diagnostics_path = DATA_DIR / "detail_extraction_diagnostics.json"
    weekly_manifest_path = DATA_DIR / "weekly_manifest.json"
    run_history_path = DATA_DIR / "run_history.jsonl"
    llm_audit_path = DATA_DIR / "llm_audit.json"
    llm_summary_path = DATA_DIR / "llm_summaries.json"
    llm_usage_path = DATA_DIR / "llm_usage.jsonl"

    report: dict[str, Any] = {"week_id": week_id, "status": "unknown", "checks": {}, "errors": []}

    add_check(report, "summary_exists", summary_path.exists(), str(summary_path))
    add_check(report, "details_exists", details_path.exists(), str(details_path))
    add_check(report, "index_exists", index_path.exists(), str(index_path))
    add_check(report, "weekly_index_exists", weekly_index_path.exists(), str(weekly_index_path))

    valid, error = valid_jsonl_file(items_path)
    add_check(report, "items_jsonl_valid", valid, error)
    valid_items, item_records_all, item_error = load_jsonl_records(items_path)
    item_records = [record for record in item_records_all if record.get("record_scope") == "item"]
    ids = [str(record.get("id") or "") for record in item_records_all]
    add_check(report, "item_ids_unique", valid_items and len(ids) == len(set(ids)), "items.jsonl 存在重复 ID")
    required_item_fields = {
        "id", "source_id", "canonical_url", "title", "summary", "evidence", "field_evidence",
        "parser_version", "record_type", "category", "record_scope", "source_quality",
        "extraction_confidence", "change_status", "content_hash", "seen_in_current_index",
        "date_text", "discovery_method",
        "semantic_content_hash", "extraction_hash", "extraction_change_status", "change_reason",
        "detail_parse_method", "detail_fetch_status", "current_run_data_reused",
    }
    add_check(
        report,
        "official_item_fields_complete",
        valid_items and all(required_item_fields <= set(record) for record in item_records),
        "条目级记录存在缺失字段",
    )
    add_check(
        report,
        "official_item_status_valid",
        all(record.get("change_status") in {"baseline", "new", "changed", "unchanged"} for record in item_records),
        "条目级 change_status 不在允许枚举中",
    )
    canonical_keys = [(record.get("source_id"), record.get("canonical_url")) for record in item_records]
    add_check(
        report,
        "official_item_canonical_unique",
        len(canonical_keys) == len(set(canonical_keys)),
        "同一来源存在重复 canonical_url",
    )
    def allowed_item_url(record: dict[str, Any]) -> bool:
        url = str(record.get("canonical_url") or "")
        parts = urlsplit(url)
        host = (parts.hostname or "").removeprefix("www.")
        if record.get("source_id") == "starlink_official_updates":
            return host == "starlink.com" and parts.path.startswith("/updates/")
        if record.get("source_id") == "spacex_official_launches":
            return host == "spacex.com" and parts.path.startswith("/launches/")
        return False

    allowed_urls = all(allowed_item_url(record) for record in item_records)
    add_check(report, "official_item_urls_allowed", allowed_urls, "条目级记录包含非允许官方路径")
    stable_ids = all(
        record.get("id")
        == hashlib.sha256(
            f"{record.get('source_id')}|{str(record.get('canonical_url') or '').rstrip('/')}".encode("utf-8")
        ).hexdigest()[:16]
        for record in item_records
    )
    add_check(report, "official_item_ids_stable", stable_ids, "条目 ID 不符合 source_id + canonical_url 规则")
    confidence_valid = all(
        record.get("source_quality") in {"medium", "high"}
        and isinstance(record.get("extraction_confidence"), (int, float))
        and 0.65 <= float(record["extraction_confidence"]) <= 0.95
        for record in item_records
    )
    add_check(report, "official_item_quality_valid", confidence_valid, "条目级质量或置信度不符合阶段 4A 规则")

    valid_state, item_state, state_error = load_json_file(item_state_path)
    add_check(report, "item_extraction_state_valid", valid_state, state_error)
    state_sources = item_state.get("sources", {}) if valid_state else {}
    add_check(
        report,
        "item_bootstrap_state_valid",
        isinstance(state_sources, dict)
        and all(
            isinstance(value, dict)
            and isinstance(value.get("bootstrap_completed"), bool)
            and bool(value.get("parser_version"))
            and "last_candidate_count" in value
            and "last_item_count" in value
            and "last_error_type" in value
            for value in state_sources.values()
        ),
        "baseline/bootstrap 状态字段缺失",
    )
    valid_item_report, item_report, report_error = load_json_file(item_report_path)
    add_check(report, "item_extraction_report_valid", valid_item_report, report_error)
    extraction_sources = item_report.get("sources", {}) if valid_item_report else {}
    required_report_fields = {
        "parser_version", "candidate_count", "detail_fetch_success", "detail_fetch_failed",
        "baseline_items", "new_items", "changed_items", "unchanged_items", "item_level_items",
        "page_level_items", "page_level_fallback", "render_fallback_status", "bootstrap_completed",
        "static_candidate_count", "rendered_candidate_count", "selected_candidate_count",
        "dominant_extracted_level", "dominant_source_quality", "title_completeness",
        "date_completeness", "evidence_completeness", "field_evidence_completeness", "warnings",
        "candidate_count_total", "static_detail_success", "rendered_detail_attempted",
        "rendered_detail_success", "reused_previous_success", "final_detail_success",
        "final_detail_failed", "final_success_rate", "failure_types", "dominant_detail_parse_method",
    }
    add_check(
        report,
        "item_extraction_report_fields_complete",
        isinstance(extraction_sources, dict)
        and all(isinstance(value, dict) and required_report_fields <= set(value) for value in extraction_sources.values()),
        "item_extraction_report.json 字段不完整",
    )
    valid_diagnostics, diagnostics, diagnostics_error = load_json_file(detail_diagnostics_path)
    add_check(report, "detail_extraction_diagnostics_valid", valid_diagnostics, diagnostics_error)
    diagnostic_sources = diagnostics.get("sources", {}) if valid_diagnostics else {}
    details = [
        detail
        for source in diagnostic_sources.values()
        if isinstance(source, dict)
        for detail in source.get("details", [])
        if isinstance(detail, dict)
    ] if isinstance(diagnostic_sources, dict) else []
    add_check(
        report,
        "detail_final_status_valid",
        all(detail.get("final_status") in {"success", "failed", "reused_previous_success"} for detail in details),
        "详情 final_status 不在允许枚举中",
    )
    add_check(
        report,
        "detail_error_types_valid",
        all(detail.get("error_type") is None or detail.get("error_type") in DETAIL_ERROR_TYPES for detail in details),
        "详情 error_type 不在允许枚举中",
    )
    counters_valid = True
    for source in diagnostic_sources.values() if isinstance(diagnostic_sources, dict) else []:
        if not isinstance(source, dict):
            counters_valid = False
            continue
        numeric_fields = ["candidate_count", "static_success", "render_attempted", "render_success", "final_success", "final_failed", "reused_previous_success"]
        counters_valid = counters_valid and all(isinstance(source.get(field), int) and source.get(field) >= 0 for field in numeric_fields)
        counters_valid = counters_valid and source.get("final_success", 0) + source.get("final_failed", 0) <= source.get("candidate_count", 0)
        counters_valid = counters_valid and source.get("render_success", 0) <= source.get("render_attempted", 0)
        rate = source.get("success_rate")
        counters_valid = counters_valid and (rate is None or isinstance(rate, (int, float)) and 0 <= rate <= 1)
    add_check(report, "detail_counts_valid", counters_valid, "详情候选、成功、失败或成功率计数不一致")
    add_check(
        report,
        "reused_history_marked",
        all(
            detail.get("final_status") != "reused_previous_success" or detail.get("current_run_data_reused") is True
            for detail in details
        )
        and all(not record.get("current_run_data_reused") or record.get("detail_fetch_status") == "failed_this_run" for record in item_records),
        "历史复用记录缺少 current_run_data_reused/detail_fetch_status 标记",
    )
    add_check(
        report,
        "parser_enrichment_not_semantic_changed",
        all(
            record.get("change_reason") != "parser_enrichment" or record.get("change_status") == "unchanged"
            for record in item_records
        ),
        "parser enrichment 被误标为事实 changed",
    )
    serialized_items = json.dumps({"items": item_records_all, "state": item_state, "report": item_report, "diagnostics": diagnostics}, ensure_ascii=False)
    forbidden_fields = {"html", "raw_html", "api_key", "smtp_password", "gitee_remote", "token"}
    observed_fields = {
        str(key).lower()
        for value in [*item_records_all, item_state, item_report]
        if isinstance(value, dict)
        for key in value
    }
    secret_shape = bool(re.search(r"sk-[A-Za-z0-9_-]{20,}|ghp_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,}", serialized_items))
    add_check(
        report,
        "official_item_outputs_safe",
        not (observed_fields & forbidden_fields) and not secret_shape and "<html" not in serialized_items.lower(),
        "条目输出包含完整 HTML、敏感字段或密钥形态",
    )
    valid, error = valid_json_file(source_status_path)
    add_check(report, "source_status_valid", valid, error)
    valid, error = valid_json_file(extraction_quality_path)
    add_check(report, "extraction_quality_valid", valid, error)
    valid, error = valid_json_file(weekly_manifest_path)
    add_check(report, "weekly_manifest_valid", valid, error)
    valid, error = valid_jsonl_file(run_history_path)
    add_check(report, "run_history_valid", valid, error)
    valid, llm_audit, error = load_json_file(llm_audit_path)
    add_check(report, "llm_audit_valid", valid, error)
    add_check(
        report,
        "llm_provider_present",
        valid and bool(str(llm_audit.get("llm_provider") or "").strip()),
        "llm_audit.json 缺少 llm_provider",
    )
    valid_usage, usage_records, usage_error = load_jsonl_records(llm_usage_path)
    add_check(report, "llm_usage_valid", valid_usage, usage_error)
    add_check(report, "llm_usage_bounded", valid_usage and len(usage_records) <= 200, "llm_usage.jsonl 超过 200 行")
    required_usage_fields = {
        "generated_at",
        "week_id",
        "llm_enabled",
        "api_called",
        "provider",
        "model",
        "status",
        "validation_status",
        "input_records_before_dedup",
        "input_records_after_dedup",
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "latency_ms",
        "error_type",
    }
    add_check(
        report,
        "llm_usage_fields_complete",
        valid_usage and all(required_usage_fields <= set(record) for record in usage_records),
        "llm_usage.jsonl 存在缺失字段",
    )
    phase4b_usage_fields = {
        "raw_candidate_records", "records_after_url_dedup", "final_core_input_records",
        "final_core_unique_urls", "reused_historical_records",
    }
    add_check(
        report,
        "llm_latest_usage_phase4b_fields",
        valid_usage and bool(usage_records) and phase4b_usage_fields <= set(usage_records[-1]),
        "最新 llm_usage 记录缺少 Phase 4B 输入统计",
    )
    serialized_usage = json.dumps(usage_records, ensure_ascii=False)
    forbidden_usage_fields = {"api_key", "openai_api_key", "deepseek_api_key", "smtp_password", "gitee_remote", "prompt", "response", "cost"}
    usage_fields = {str(key).lower() for record in usage_records for key in record}
    usage_has_secret_shape = bool(
        re.search(r"sk-[A-Za-z0-9_-]{20,}|ghp_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,}", serialized_usage)
    )
    add_check(
        report,
        "llm_usage_has_no_secrets",
        valid_usage and not (usage_fields & forbidden_usage_fields) and not usage_has_secret_shape,
        "llm_usage.jsonl 包含禁止的敏感字段或值线索",
    )
    before_dedup = llm_audit.get("input_records_before_dedup") if valid else None
    after_dedup = llm_audit.get("input_records_after_dedup") if valid else None
    removed = llm_audit.get("duplicate_records_removed") if valid else None
    dedup_valid = (
        isinstance(before_dedup, int)
        and isinstance(after_dedup, int)
        and isinstance(removed, int)
        and 0 <= after_dedup <= before_dedup
        and removed >= 0
        and removed == before_dedup - after_dedup
    )
    add_check(report, "llm_dedup_counts_valid", dedup_valid, "LLM 输入去重计数不一致")
    records_after_url_dedup = llm_audit.get("records_after_url_dedup")
    final_core_input_records = llm_audit.get("final_core_input_records")
    add_check(
        report,
        "llm_final_core_counts_valid",
        isinstance(records_after_url_dedup, int)
        and isinstance(final_core_input_records, int)
        and 0 <= final_core_input_records <= records_after_url_dedup,
        "最终核心输入数量大于 URL 去重后记录",
    )
    usage = llm_audit.get("usage", {}) if isinstance(llm_audit.get("usage"), dict) else {}
    total_tokens = usage.get("total_tokens")
    latency_ms = usage.get("latency_ms")
    add_check(
        report,
        "llm_total_tokens_valid",
        total_tokens is None or (isinstance(total_tokens, int) and not isinstance(total_tokens, bool) and total_tokens >= 0),
        "total_tokens 必须为 null 或非负整数",
    )
    add_check(
        report,
        "llm_latency_valid",
        latency_ms is None or (isinstance(latency_ms, (int, float)) and not isinstance(latency_ms, bool) and latency_ms >= 0),
        "latency_ms 必须为 null 或非负数",
    )
    add_check(
        report,
        "llm_status_present",
        valid and bool(str(llm_audit.get("llm_status") or "").strip()),
        "llm_audit.json 缺少 llm_status",
    )
    add_check(
        report,
        "llm_model_present",
        valid and "model" in llm_audit,
        "llm_audit.json 缺少 model 字段",
    )
    llm_status = str(llm_audit.get("llm_status") or "unknown") if valid else "unknown"
    if llm_status == "generated":
        valid_summary, summary_data, error = load_json_file(llm_summary_path)
        add_check(report, "llm_summary_valid_when_generated", valid_summary, error)
        add_check(
            report,
            "llm_validation_passed_when_generated",
            llm_audit.get("validation_status") == "passed",
            "generated 状态下 validation_status 不是 passed",
        )
        summary = summary_data.get("summary", {}) if isinstance(summary_data.get("summary"), dict) else {}
        references_valid = True
        for section_name in ["key_points", "source_based_notes"]:
            section = summary.get(section_name, [])
            for point in section if isinstance(section, list) else []:
                if not isinstance(point, dict):
                    references_valid = False
                    continue
                ids = [str(value) for value in point.get("source_record_ids", []) if value]
                urls = [str(value) for value in point.get("source_urls", []) if value]
                if not ids or not urls or len(ids) != len(set(ids)) or len(urls) != len(set(urls)):
                    references_valid = False
        add_check(report, "llm_generated_references_valid", references_valid, "生成摘要存在缺失或重复来源引用")
    elif llm_summary_path.exists():
        valid_summary, error = valid_json_file(llm_summary_path)
        add_check(report, "llm_summary_valid_if_present", valid_summary, error)
    else:
        add_check(report, "llm_summary_optional", True)

    summary_text = read_text(summary_path)
    add_check(report, "summary_has_core_conclusions", "本周核心结论" in summary_text, "summary 缺少“本周核心结论”")
    add_check(report, "summary_has_source_overview", "来源状态概览" in summary_text, "summary 缺少“来源状态概览”")
    add_check(report, "summary_has_quality_overview", "解析质量概览" in summary_text, "summary 缺少“解析质量概览”")
    add_check(report, "summary_has_llm_section", "大模型辅助摘要" in summary_text, "summary 缺少“大模型辅助摘要”")
    add_check(report, "summary_has_llm_provider", "LLM Provider" in summary_text, "summary 缺少 LLM Provider")
    add_check(report, "summary_has_page_monitoring", "页面级监测解释" in summary_text, "summary 缺少页面级监测解释")
    add_check(report, "summary_has_input_dedup", "原始候选记录" in summary_text, "summary 缺少三层输入统计")
    add_check(report, "summary_has_structured_official_items", "## 结构化官方条目" in summary_text, "summary 缺少结构化官方条目")
    baseline_total = sum(int(value.get("baseline_items") or 0) for value in extraction_sources.values() if isinstance(value, dict)) if isinstance(extraction_sources, dict) else 0
    add_check(
        report,
        "summary_has_baseline_explanation",
        baseline_total == 0 or "baseline 仅表示建立采集基线，不代表这些内容在本周发布" in summary_text,
        "summary 缺少 baseline 非新增说明",
    )
    add_check(
        report,
        "summary_zero_baseline_wording_valid",
        baseline_total > 0 or "本次为条目级解析器首次成功运行" not in summary_text,
        "baseline=0 时 summary 仍显示首次建库",
    )
    add_check(report, "summary_has_detail_parsing", "### 详情解析情况" in summary_text, "summary 缺少详情解析情况")
    if valid and llm_audit.get("llm_enabled") is True:
        add_check(
            report,
            "summary_llm_enabled_wording_valid",
            "当前自动化运行未启用 LLM" not in summary_text,
            "LLM enabled=true 时 summary 仍显示当前未启用",
        )

    details_text = read_text(details_path)
    add_check(report, "details_has_source_status", "来源状态诊断" in details_text, "details 缺少“来源状态诊断”")
    add_check(report, "details_has_quality", "解析质量诊断" in details_text, "details 缺少“解析质量诊断”")
    add_check(report, "details_has_items", "采集条目明细" in details_text, "details 缺少“采集条目明细”")
    add_check(report, "details_has_llm_audit", "大模型摘要审计" in details_text, "details 缺少“大模型摘要审计”")
    add_check(report, "details_has_llm_provider", "LLM Provider" in details_text, "details 缺少 LLM Provider")
    add_check(report, "details_has_page_monitoring", "页面级监测解释" in details_text, "details 缺少页面级监测解释")
    add_check(report, "details_has_input_dedup", "原始候选记录" in details_text, "details 缺少三层输入统计")
    add_check(report, "details_has_official_item_diagnostics", "## 官方条目解析诊断" in details_text, "details 缺少官方条目解析诊断")
    add_check(report, "details_has_detail_diagnostics", "## 官方详情页解析诊断" in details_text, "details 缺少官方详情页解析诊断")
    add_check(report, "details_has_detail_failure_types", "### 详情失败类型" in details_text, "details 缺少详情失败类型")

    index_text = read_text(index_path)
    add_check(report, "index_links_summary", f"./{week_id}-summary.md" in index_text, "兼容索引缺少 summary 相对链接")
    add_check(report, "index_links_details", f"./{week_id}-details.md" in index_text, "兼容索引缺少 details 相对链接")

    weekly_index_text = read_text(weekly_index_path)
    add_check(report, "weekly_index_has_week", week_id in weekly_index_text, "weekly/index.md 缺少当前 ISO 周编号")

    report["status"] = "passed" if not report["errors"] else "failed"
    return report


def print_text_report(report: dict[str, Any]) -> None:
    checks = report["checks"]
    print("开始检查周报输出。")
    print(f"检查周编号：{report['week_id']}")
    print(f"summary 文档：{'存在' if checks.get('summary_exists') else '缺失'}")
    print(f"details 文档：{'存在' if checks.get('details_exists') else '缺失'}")
    print(f"兼容索引文档：{'存在' if checks.get('index_exists') else '缺失'}")
    print(f"weekly/index.md：{'存在' if checks.get('weekly_index_exists') else '缺失'}")
    print(f"items.jsonl：{'合法' if checks.get('items_jsonl_valid') else '异常'}")
    print(f"source_status.json：{'合法' if checks.get('source_status_valid') else '异常'}")
    print(f"extraction_quality.json：{'合法' if checks.get('extraction_quality_valid') else '异常'}")
    print(f"weekly_manifest.json：{'合法' if checks.get('weekly_manifest_valid') else '异常'}")
    print(f"run_history.jsonl：{'合法' if checks.get('run_history_valid') else '异常'}")
    print(f"llm_audit.json：{'合法' if checks.get('llm_audit_valid') else '异常'}")
    print(f"llm_usage.jsonl：{'合法' if checks.get('llm_usage_valid') else '异常'}")
    print(f"detail_extraction_diagnostics.json：{'合法' if checks.get('detail_extraction_diagnostics_valid') else '异常'}")
    print(
        "llm_summaries.json："
        + ("合法或可选" if checks.get("llm_summary_valid_when_generated") or checks.get("llm_summary_valid_if_present") or checks.get("llm_summary_optional") else "异常")
    )
    if report["errors"]:
        print("检查发现问题：")
        for error in report["errors"]:
            print(f"- {error}")
    print(f"检查完成：{report['status']}")


def main() -> int:
    parser = argparse.ArgumentParser(description="检查本周周报输出质量。")
    parser.add_argument("--week-id", default=current_week_id(), help="指定 ISO 周编号，例如 2026-W25。")
    parser.add_argument("--strict", action="store_true", help="严格模式：任何关键检查失败时返回非 0。")
    parser.add_argument("--json", action="store_true", help="输出 JSON 格式检查报告。")
    args = parser.parse_args()

    report = build_report(args.week_id)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print_text_report(report)

    if args.strict and report["status"] != "passed":
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
