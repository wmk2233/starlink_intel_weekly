from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from collect_sources import (
    DETAIL_EXTRACTION_DIAGNOSTICS_FILE,
    EXTRACTION_QUALITY_FILE,
    ITEMS_FILE,
    ITEM_EXTRACTION_REPORT_FILE,
    ITEM_EXTRACTION_STATE_FILE,
    SOURCE_STATUS_FILE,
    collect_all_sources,
    load_extraction_quality,
    load_items,
    load_source_status,
)
from llm_summarize import (
    DEFAULT_MAX_USAGE_RECORDS,
    DEFAULT_DEEPSEEK_BASE_URL,
    DEFAULT_DEEPSEEK_MODEL,
    DEFAULT_PROVIDER,
    LLM_AUDIT_FILE,
    LLM_SUMMARY_FILE,
    LLM_USAGE_FILE,
    run_llm_summary,
)
from item_lifecycle import (
    DEFAULT_DETAIL_FAILURE_ATTENTION_THRESHOLD,
    DEFAULT_LONG_ABSENCE_MIN_DAYS,
    DEFAULT_LONG_ABSENCE_OBSERVATION_THRESHOLD,
    DEFAULT_MAX_ITEM_VERSIONS_PER_RECORD,
    DEFAULT_MAX_LIFECYCLE_EVENTS,
    ITEM_LIFECYCLE_STATE_FILE,
    ITEM_VERSIONS_FILE,
    LIFECYCLE_EVENTS_FILE,
    LIFECYCLE_REPORT_FILE,
    load_jsonl as load_lifecycle_jsonl,
    load_lifecycle_report,
    load_lifecycle_state,
    safe_positive_int,
)
from send_email import send_weekly_email
from operational_health import (
    ALERT_EVENTS_FILE,
    ALERT_REPORT_FILE,
    ALERT_STATE_FILE,
    RUN_HEALTH_FILE,
    RUN_HEALTH_HISTORY_FILE,
    SEVERITY_SAFETY_NOTE,
    build_run_health_data,
    default_alert_state,
    evaluate_alerts_data,
    load_json as load_operational_json,
    load_jsonl as load_operational_jsonl,
    policy_from_env as operational_policy_from_env,
    write_alert_evaluation,
    write_health_evaluation,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WEEKLY_DIR = PROJECT_ROOT / "weekly"
DOCS_DIR = PROJECT_ROOT / "docs"
KNOWLEDGE_BASE = DOCS_DIR / "starlink_knowledge_base.md"
WEEKLY_ARCHIVE_INDEX = WEEKLY_DIR / "index.md"
WEEKLY_MANIFEST_FILE = PROJECT_ROOT / "data" / "weekly_manifest.json"
RUN_HISTORY_FILE = PROJECT_ROOT / "data" / "run_history.jsonl"
LIFECYCLE_REPLAY_REPORT_FILE = PROJECT_ROOT / "data" / "lifecycle_replay_report.json"
DETAIL_HISTORY_HEADING = "## 9. 自动化测试记录"
LEGACY_HISTORY_HEADINGS = [
    "## 9. 自动化测试记录",
    "## 7. 自动化测试记录",
    "## 6. 自动化测试记录",
    "## 4. 自动化测试记录",
    "## 自动化测试记录",
]
CONNECTED_SOURCES_HEADING = "## 已接入来源"
SOURCE_CHANGE_HEADING = "## 来源状态与变化检测"
QUALITY_HEADING = "## 来源解析质量诊断"
OUTPUT_STRUCTURE_HEADING = "## 周报输出结构"
ARCHIVE_HEADING = "## 周报归档与历史索引"
LLM_HEADING = "## 阶段 3C LLM 去重、变化分层与用量审计"
LEGACY_LLM_HEADING = "## 阶段 3A 大模型摘要边界"
LEGACY_LLM_HEADING_3B = "## 阶段 3B DeepSeek Provider 与大模型摘要边界"


def get_run_metadata(send_email_enabled: bool, collect_enabled: bool, output_mode: str) -> dict[str, str]:
    now = datetime.now().astimezone()
    iso = now.isocalendar()
    week_id = f"{iso.year}-W{iso.week:02d}"
    return {
        "run_time": now.strftime("%Y-%m-%d %H:%M:%S %Z%z"),
        "run_iso": now.isoformat(timespec="seconds"),
        "iso_week": week_id,
        "environment": f"{platform.system()} {platform.release()}",
        "python_version": platform.python_version(),
        "send_email": "是" if send_email_enabled else "否",
        "email_delivery_mode": "run_weekly.py 末尾发送" if send_email_enabled else "当前运行不发送邮件",
        "email_status_at_report": "pending_at_render_time" if send_email_enabled else "not_applicable",
        "collect_sources": "是" if collect_enabled else "否",
        "quality_generated": "否",
        "output_mode": output_mode,
        "source_names": "无",
        "source_item_count": "0",
        "new_items": "0",
        "changed_items": "0",
        "unchanged_items": "0",
        "baseline_items": "0",
        "item_level_items": "0",
        "page_level_items": "0",
        "health_status": "unknown",
        "page_change_status": "unknown",
        "http_status": "unknown",
        "last_checked_at": "未知",
        "source_status_path": str(SOURCE_STATUS_FILE),
        "items_path": str(ITEMS_FILE),
        "quality_path": str(EXTRACTION_QUALITY_FILE),
        "item_extraction_state_path": "data/item_extraction_state.json",
        "item_extraction_report_path": "data/item_extraction_report.json",
        "detail_extraction_diagnostics_path": "data/detail_extraction_diagnostics.json",
        "item_lifecycle_state_path": "data/item_lifecycle_state.json",
        "item_versions_path": "data/item_versions.jsonl",
        "lifecycle_events_path": "data/lifecycle_events.jsonl",
        "lifecycle_report_path": "data/lifecycle_report.json",
        "lifecycle_initialized": "0",
        "lifecycle_new_items": "0",
        "lifecycle_changed_items": "0",
        "lifecycle_extraction_improved": "0",
        "lifecycle_temporarily_missing": "0",
        "lifecycle_long_absent": "0",
        "lifecycle_fetch_failed": "0",
        "lifecycle_recovered": "0",
        "lifecycle_reappeared": "0",
        "lifecycle_attention_items": "0",
        "lifecycle_new_semantic_versions": "0",
        "lifecycle_new_extraction_revisions": "0",
        "lifecycle_event_count": "0",
        "lifecycle_replay_report_path": "data/lifecycle_replay_report.json",
        "alert_state_path": "data/alert_state.json",
        "alert_events_path": "data/alert_events.jsonl",
        "alert_report_path": "data/alert_report.json",
        "run_health_path": "data/run_health.json",
        "run_health_history_path": "data/run_health_history.jsonl",
        "overall_health": "unknown",
        "overall_alert_status": "unknown",
        "new_alerts": "0",
        "resolved_alerts": "0",
        "open_warning_alerts": "0",
        "open_high_alerts": "0",
        "open_critical_alerts": "0",
        "item_extraction_overview": "暂无官方条目抽取结果。",
        "detail_extraction_overview": "暂无官方详情解析结果。",
        "detail_failure_overview": "本轮没有详情解析失败。",
        "historical_reuse_note": "",
        "connected_source_count": "0",
        "reachable_source_count": "0",
        "page_changed_source_count": "0",
        "overall_quality": "unknown",
        "source_overview": "",
        "quality_overview": "",
        "summary_path": "",
        "details_path": "",
        "index_path": "",
        "weekly_archive_index_path": "weekly/index.md",
        "weekly_manifest_path": "data/weekly_manifest.json",
        "run_history_path": "data/run_history.jsonl",
        "quality_check_status": "skipped",
        "llm_enabled": "false",
        "llm_provider": DEFAULT_PROVIDER,
        "llm_status": "skipped",
        "llm_summary_generated": "false",
        "llm_model": DEFAULT_DEEPSEEK_MODEL,
        "llm_base_url_label": "deepseek_default",
        "llm_input_records": "0",
        "llm_input_records_before_dedup": "0",
        "llm_input_records_after_dedup": "0",
        "llm_duplicate_records_removed": "0",
        "llm_unique_source_urls": "0",
        "llm_raw_candidate_records": "0",
        "llm_records_after_url_dedup": "0",
        "llm_final_core_input_records": "0",
        "llm_final_core_unique_urls": "0",
        "llm_reused_historical_records": "0",
        "llm_current_status_text": "代码层面 LLM 默认关闭；当前自动化运行未启用 LLM，因此不会调用外部模型。",
        "llm_output_record_references_before_dedup": "0",
        "llm_output_record_references_after_dedup": "0",
        "llm_output_url_references_before_dedup": "0",
        "llm_output_url_references_after_dedup": "0",
        "llm_invalid_record_ids_removed": "0",
        "llm_invalid_urls_removed": "0",
        "llm_missing_record_ids_repaired": "0",
        "llm_missing_urls_repaired": "0",
        "llm_key_points_removed_without_sources": "0",
        "llm_reference_alignment_status": "not_run",
        "llm_prompt_tokens": "unknown",
        "llm_completion_tokens": "unknown",
        "llm_total_tokens": "unknown",
        "llm_latency_ms": "unknown",
        "llm_monitoring_overview": "暂无页面级监测解释。",
        "llm_validation_status": "skipped",
        "llm_reason": "LLM is disabled.",
        "llm_audit_path": "data/llm_audit.json",
        "llm_summary_path": "data/llm_summaries.json",
        "llm_usage_path": "data/llm_usage.jsonl",
        "llm_strict_source": "true",
        "llm_page_level_no_fact_expansion": "true",
        "llm_errors": "",
        "llm_warnings": "",
    }


def apply_email_reporting_mode(
    meta: dict[str, str],
    *,
    send_email_enabled: bool,
    no_email_requested: bool,
    dry_run: bool,
    github_actions: bool,
) -> None:
    if github_actions and no_email_requested and not dry_run:
        meta["email_delivery_mode"] = "GitHub Actions 后续独立步骤"
        meta["email_status_at_report"] = "pending_at_render_time"
    elif send_email_enabled:
        meta["email_delivery_mode"] = "run_weekly.py 末尾发送"
        meta["email_status_at_report"] = "pending_at_render_time"
    else:
        meta["email_delivery_mode"] = "当前运行不发送邮件"
        meta["email_status_at_report"] = "not_applicable"


def weekly_output_paths(week_id: str) -> dict[str, Path]:
    return {
        "summary": WEEKLY_DIR / f"{week_id}-summary.md",
        "details": WEEKLY_DIR / f"{week_id}-details.md",
        "index": WEEKLY_DIR / f"{week_id}.md",
    }


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def relative_project_path(path: Path) -> str:
    return path.relative_to(PROJECT_ROOT).as_posix()


def optional_number(value: object) -> int | float | None:
    if value in (None, "", "unknown", "未知"):
        return None
    try:
        number = float(str(value))
    except (TypeError, ValueError):
        return None
    return int(number) if number.is_integer() else number


def display_metric(value: object) -> str:
    return "unknown" if value is None else str(value)


def escape_table_cell(value: object) -> str:
    text = "" if value is None else str(value)
    text = text.replace("\n", " ").replace("\r", " ")
    return text.replace("|", "\\|").strip()


def truncate_text(value: object, max_length: int = 500) -> str:
    text = escape_table_cell(value)
    if len(text) <= max_length:
        return text
    return text[: max_length - 1].rstrip() + "…"


def format_link(url: object, label: str = "链接") -> str:
    text = str(url or "").strip()
    return f"[{label}]({text})" if text else ""


def source_count(source_statuses: dict[str, dict[str, object]]) -> int:
    return len(source_statuses)


def reachable_count(source_statuses: dict[str, dict[str, object]]) -> int:
    return sum(1 for status in source_statuses.values() if status.get("health_status") == "reachable")


def page_changed_count(source_statuses: dict[str, dict[str, object]]) -> int:
    return sum(1 for status in source_statuses.values() if status.get("change_status") == "changed")


def overall_quality_label(source_statuses: dict[str, dict[str, object]], quality_sources: dict[str, dict[str, object]]) -> str:
    order = {"high": 3, "medium": 2, "low": 1, "unknown": 0}
    qualities: list[str] = []
    for source_id, status in source_statuses.items():
        quality = quality_sources.get(source_id, {})
        qualities.append(str(quality.get("dominant_source_quality") or status.get("dominant_source_quality") or "unknown"))
    if not qualities:
        return "unknown"
    min_quality = min(qualities, key=lambda item: order.get(item, 0))
    return f"{min_quality}（以当前规则解析完整度为准）"


def dominant_quality_value(source_statuses: dict[str, dict[str, object]], quality_sources: dict[str, dict[str, object]]) -> str:
    label = overall_quality_label(source_statuses, quality_sources)
    return label.split("（", 1)[0] if label else "unknown"


def dominant_extracted_level_value(source_statuses: dict[str, dict[str, object]], quality_sources: dict[str, dict[str, object]]) -> str:
    order = {"item_level": 3, "link_level": 2, "page_level": 1, "unknown": 0}
    levels: list[str] = []
    for source_id, status in source_statuses.items():
        quality = quality_sources.get(source_id, {})
        levels.append(str(quality.get("dominant_extracted_level") or status.get("dominant_extracted_level") or "unknown"))
    if not levels:
        return "unknown"
    return min(levels, key=lambda item: order.get(item, 0))


def quality_sources_from_data(extraction_quality: dict[str, object] | None) -> dict[str, dict[str, object]]:
    if not isinstance(extraction_quality, dict):
        return {}
    sources = extraction_quality.get("sources", {})
    return sources if isinstance(sources, dict) else {}


def render_summary_source_status_table(
    source_statuses: dict[str, dict[str, object]],
    quality_sources: dict[str, dict[str, object]],
) -> str:
    if not source_statuses:
        return "本次没有来源状态记录。"

    rows = [
        "| 来源 | 可达性 | 页面变化状态 | 新增 | 变化 | 未变化 | 主导解析层级 | 主导质量 |",
        "|---|---|---|---:|---:|---:|---|---|",
    ]
    for source_id, status in source_statuses.items():
        quality = quality_sources.get(source_id, {})
        rows.append(
            "| "
            + " | ".join(
                [
                    escape_table_cell(status.get("source_name") or source_id),
                    escape_table_cell(status.get("health_status", "unknown")),
                    escape_table_cell(status.get("change_status", "unknown")),
                    escape_table_cell(status.get("new_items", 0)),
                    escape_table_cell(status.get("changed_items", 0)),
                    escape_table_cell(status.get("unchanged_items", 0)),
                    escape_table_cell(quality.get("dominant_extracted_level") or status.get("dominant_extracted_level") or "unknown"),
                    escape_table_cell(quality.get("dominant_source_quality") or status.get("dominant_source_quality") or "unknown"),
                ]
            )
            + " |"
        )
    return "\n".join(rows)


def render_detail_source_status_table(source_statuses: dict[str, dict[str, object]]) -> str:
    if not source_statuses:
        return "本次没有来源状态记录。"

    rows = [
        "| 来源 | 类别 | 类型 | 可信度 | 可达性 | 页面变化状态 | HTTP状态 | 最近检查时间 | page_hash |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for status in source_statuses.values():
        rows.append(
            "| "
            + " | ".join(
                [
                    escape_table_cell(status.get("source_name", "")),
                    escape_table_cell(status.get("category", "")),
                    escape_table_cell(status.get("source_type", "")),
                    escape_table_cell(status.get("reliability_tier", "")),
                    escape_table_cell(status.get("health_status", "")),
                    escape_table_cell(status.get("change_status", "")),
                    escape_table_cell(status.get("http_status", "")),
                    escape_table_cell(status.get("last_checked_at", "")),
                    escape_table_cell(status.get("current_page_hash", "")),
                ]
            )
            + " |"
        )
    return "\n".join(rows)


def render_change_detection_table(source_statuses: dict[str, dict[str, object]], detail: bool = False) -> str:
    if not source_statuses:
        return "本次没有来源变化检测记录。"

    if detail:
        rows = [
            "| 来源 | 新增条目数 | 内容变化条目数 | 未变化条目数 | 页面级变化状态 | 最近变化时间 |",
            "|---|---:|---:|---:|---|---|",
        ]
    else:
        rows = [
            "| 来源 | 新增条目数 | 内容变化条目数 | 未变化条目数 | 页面级变化状态 |",
            "|---|---:|---:|---:|---|",
        ]
    for status in source_statuses.values():
        values = [
            escape_table_cell(status.get("source_name", "")),
            escape_table_cell(status.get("new_items", 0)),
            escape_table_cell(status.get("changed_items", 0)),
            escape_table_cell(status.get("unchanged_items", 0)),
            escape_table_cell(status.get("change_status", "")),
        ]
        if detail:
            values.append(escape_table_cell(status.get("last_changed_at", "")))
        rows.append("| " + " | ".join(values) + " |")
    return "\n".join(rows)


def render_summary_quality_table(
    quality_sources: dict[str, dict[str, object]],
    source_statuses: dict[str, dict[str, object]],
) -> str:
    if not quality_sources and not source_statuses:
        return "本次没有解析质量诊断记录。"

    rows = [
        "| 来源 | 主导解析层级 | 主导质量 | 平均置信度 | 静态候选 | 渲染候选 | 候选总数 |",
        "|---|---|---|---:|---:|---:|---:|",
    ]
    ordered_ids = list(source_statuses.keys()) or list(quality_sources.keys())
    for source_id in ordered_ids:
        quality = quality_sources.get(source_id, {})
        status = source_statuses.get(source_id, {})
        rows.append(
            "| "
            + " | ".join(
                [
                    escape_table_cell(quality.get("source_name") or status.get("source_name") or source_id),
                    escape_table_cell(quality.get("dominant_extracted_level") or status.get("dominant_extracted_level") or "unknown"),
                    escape_table_cell(quality.get("dominant_source_quality") or status.get("dominant_source_quality") or "unknown"),
                    escape_table_cell(quality.get("average_confidence") or status.get("average_confidence") or 0),
                    escape_table_cell(quality.get("static_candidate_count") or status.get("static_candidate_count") or 0),
                    escape_table_cell(quality.get("rendered_candidate_count") or status.get("rendered_candidate_count") or 0),
                    escape_table_cell(quality.get("candidate_count_total") or status.get("candidate_count_total") or 0),
                ]
            )
            + " |"
        )
    return "\n".join(rows)


def render_detail_quality_table(
    quality_sources: dict[str, dict[str, object]],
    source_statuses: dict[str, dict[str, object]],
) -> str:
    if not quality_sources and not source_statuses:
        return "本次没有解析质量诊断记录。"

    rows = [
        "| 来源 | 主导解析层级 | 主导质量 | 平均置信度 | 页面级 | 链接级 | 条目级 | 静态候选 | 渲染候选 | 候选总数 | 解析器版本 |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    ordered_ids = list(source_statuses.keys()) or list(quality_sources.keys())
    for source_id in ordered_ids:
        quality = quality_sources.get(source_id, {})
        status = source_statuses.get(source_id, {})
        level_counts = quality.get("level_counts", {}) if isinstance(quality.get("level_counts"), dict) else {}
        rows.append(
            "| "
            + " | ".join(
                [
                    escape_table_cell(quality.get("source_name") or status.get("source_name") or source_id),
                    escape_table_cell(quality.get("dominant_extracted_level") or status.get("dominant_extracted_level") or "unknown"),
                    escape_table_cell(quality.get("dominant_source_quality") or status.get("dominant_source_quality") or "unknown"),
                    escape_table_cell(quality.get("average_confidence") or status.get("average_confidence") or 0),
                    escape_table_cell(level_counts.get("page_level", 0)),
                    escape_table_cell(level_counts.get("link_level", 0)),
                    escape_table_cell(level_counts.get("item_level", 0)),
                    escape_table_cell(quality.get("static_candidate_count") or status.get("static_candidate_count") or 0),
                    escape_table_cell(quality.get("rendered_candidate_count") or status.get("rendered_candidate_count") or 0),
                    escape_table_cell(quality.get("candidate_count_total") or status.get("candidate_count_total") or 0),
                    escape_table_cell(quality.get("parser_version") or status.get("parser_version") or "unknown"),
                ]
            )
            + " |"
        )
    return "\n".join(rows)


def group_items_by_source(source_items: list[dict[str, object]], max_source_items: int) -> dict[str, list[dict[str, object]]]:
    grouped: dict[str, list[dict[str, object]]] = {}
    for item in source_items:
        source_id = str(item.get("source_id") or "unknown")
        grouped.setdefault(source_id, [])
        if len(grouped[source_id]) < max_source_items:
            grouped[source_id].append(item)
    return grouped


def render_changed_items_summary(source_items: list[dict[str, object]]) -> str:
    changed_items = [
        item
        for item in source_items
        if item.get("record_scope") == "item"
        and item.get("change_status") in {"new", "changed"}
        and not (
            item.get("source_id") == "spacex_official_launches"
            and item.get("starlink_relevance") != "direct"
        )
    ]
    if not changed_items:
        return "本周未检测到新增或内容变化的结构化官方条目。"

    rows = [
        "| 标题 | 来源 | 官方日期文本 | 状态 | 解析层级 | 质量 | 官方链接 |",
        "|---|---|---|---|---|---|---|",
    ]
    for item in changed_items:
        rows.append(
            "| "
            + " | ".join(
                [
                    escape_table_cell(item.get("title", "")),
                    escape_table_cell(item.get("source_name", "")),
                    escape_table_cell(item.get("date_text") or item.get("published_date_text") or "未知"),
                    escape_table_cell(item.get("change_status", "")),
                    escape_table_cell(item.get("extracted_level", "unknown")),
                    escape_table_cell(item.get("source_quality", "unknown")),
                    format_link(item.get("url")),
                ]
            )
            + " |"
        )
    return "\n".join(rows)


def render_official_item_quality_table(item_report: dict[str, object]) -> str:
    sources = item_report.get("sources", {}) if isinstance(item_report, dict) else {}
    if not isinstance(sources, dict) or not sources:
        return "本次没有官方条目抽取报告。"
    rows = [
        "| 来源 | 解析器 | 静态候选 | 渲染候选 | 候选总数 | 静态详情成功 | 渲染详情成功 | 最终成功 | 失败 | 成功率 | Baseline | 新增 | 变化 | 未变化 | 层级 | 质量 |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|",
    ]
    for source_id, raw in sources.items():
        report = raw if isinstance(raw, dict) else {}
        rows.append(
            "| "
            + " | ".join(
                [
                    escape_table_cell(report.get("source_name") or source_id),
                    escape_table_cell(report.get("parser_version") or "unknown"),
                    escape_table_cell(report.get("static_candidate_count", 0)),
                    escape_table_cell(report.get("rendered_candidate_count", 0)),
                    escape_table_cell(report.get("candidate_count_total", report.get("candidate_count", 0))),
                    escape_table_cell(report.get("static_detail_success", 0)),
                    escape_table_cell(report.get("rendered_detail_success", 0)),
                    escape_table_cell(report.get("final_detail_success", report.get("detail_fetch_success", 0))),
                    escape_table_cell(report.get("final_detail_failed", report.get("detail_fetch_failed", 0))),
                    "unknown" if report.get("final_success_rate") is None else f"{float(report.get('final_success_rate')):.0%}",
                    escape_table_cell(report.get("baseline_items", 0)),
                    escape_table_cell(report.get("new_items", 0)),
                    escape_table_cell(report.get("changed_items", 0)),
                    escape_table_cell(report.get("unchanged_items", 0)),
                    escape_table_cell(report.get("dominant_extracted_level", "unknown")),
                    escape_table_cell(report.get("dominant_source_quality", "unknown")),
                ]
            )
            + " |"
        )
    return "\n".join(rows)


def render_detail_parsing_overview(item_report: dict[str, object]) -> str:
    sources = item_report.get("sources", {}) if isinstance(item_report, dict) else {}
    if not isinstance(sources, dict) or not sources:
        return "本次没有官方详情解析报告。"
    rows = [
        "| 来源 | 静态候选 | 渲染候选 | 候选总数 | 静态详情成功 | 渲染详情成功 | 最终成功 | 失败 | 成功率 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for source_id, raw in sources.items():
        report = raw if isinstance(raw, dict) else {}
        rate = report.get("final_success_rate")
        rate_text = "unknown" if rate is None else f"{float(rate):.0%}"
        rows.append(
            f"| {escape_table_cell(report.get('source_name') or source_id)} | "
            f"{report.get('static_candidate_count', 0)} | {report.get('rendered_candidate_count', 0)} | "
            f"{report.get('candidate_count_total', report.get('candidate_count', 0))} | "
            f"{report.get('static_detail_success', 0)} | {report.get('rendered_detail_success', 0)} | "
            f"{report.get('final_detail_success', 0)} | {report.get('final_detail_failed', 0)} | {rate_text} |"
        )
    return "\n".join(rows)


def render_detail_failure_overview(item_report: dict[str, object]) -> str:
    sources = item_report.get("sources", {}) if isinstance(item_report, dict) else {}
    rows = ["| 来源 | 失败类型 | 数量 |", "|---|---|---:|"]
    if isinstance(sources, dict):
        for source_id, raw in sources.items():
            report = raw if isinstance(raw, dict) else {}
            failure_types = report.get("failure_types", {})
            if not isinstance(failure_types, dict):
                continue
            for error_type, count in sorted(failure_types.items()):
                rows.append(
                    f"| {escape_table_cell(report.get('source_name') or source_id)} | "
                    f"{escape_table_cell(error_type)} | {int(count or 0)} |"
                )
    return "本轮没有详情解析失败。" if len(rows) == 2 else "\n".join(rows)


def render_detail_diagnostics_table(diagnostics: dict[str, object], max_records: int) -> str:
    sources = diagnostics.get("sources", {}) if isinstance(diagnostics, dict) else {}
    rows = [
        "| 来源 | 详情 URL | 静态状态 | 是否渲染 | 渲染状态 | 最终状态 | 最终方法 | 错误类型 | 是否复用历史记录 |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    if isinstance(sources, dict):
        for source_id, raw in sources.items():
            source = raw if isinstance(raw, dict) else {}
            details = source.get("details", [])
            if not isinstance(details, list):
                continue
            for detail in details:
                if not isinstance(detail, dict) or len(rows) - 2 >= max_records:
                    break
                static = detail.get("static", {}) if isinstance(detail.get("static"), dict) else {}
                render = detail.get("render", {}) if isinstance(detail.get("render"), dict) else {}
                rows.append(
                    "| "
                    + " | ".join(
                        [
                            escape_table_cell(source.get("source_name") or source_id),
                            format_link(detail.get("canonical_url"), "详情"),
                            escape_table_cell(static.get("parse_status", "unknown")),
                            "是" if render.get("attempted") else "否",
                            escape_table_cell(render.get("parse_status", "not_attempted")),
                            escape_table_cell(detail.get("final_status", "unknown")),
                            escape_table_cell(detail.get("final_method") or "none"),
                            escape_table_cell(detail.get("error_type") or "none"),
                            "是" if detail.get("current_run_data_reused") else "否",
                        ]
                    )
                    + " |"
                )
    return "当前没有逐候选详情诊断。" if len(rows) == 2 else "\n".join(rows)


def render_structured_official_items(source_items: list[dict[str, object]], item_report: dict[str, object]) -> str:
    sources = item_report.get("sources", {}) if isinstance(item_report, dict) else {}
    reports = list(sources.values()) if isinstance(sources, dict) else []
    baseline_count = sum(int(report.get("baseline_items") or 0) for report in reports if isinstance(report, dict))
    overview = [
        "| 来源 | 候选 | 详情成功 | Baseline | 新增 | 变化 | 未变化 | 层级 | 质量 |",
        "|---|---:|---:|---:|---:|---:|---:|---|---|",
    ]
    quality_rows = [
        "| 来源 | Item-level 数量 | 标题完整度 | 日期完整度 | 证据完整度 | 页面级 fallback |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for report in reports:
        overview.append(
            f"| {escape_table_cell(report.get('source_name') or report.get('source_id'))} | "
            f"{report.get('selected_candidate_count', report.get('candidate_count', 0))} | "
            f"{report.get('detail_fetch_success', 0)} | {report.get('baseline_items', 0)} | "
            f"{report.get('new_items', 0)} | {report.get('changed_items', 0)} | {report.get('unchanged_items', 0)} | "
            f"{escape_table_cell(report.get('dominant_extracted_level', 'unknown'))} | "
            f"{escape_table_cell(report.get('dominant_source_quality', 'unknown'))} |"
        )
        quality_rows.append(
            f"| {escape_table_cell(report.get('source_name') or report.get('source_id'))} | "
            f"{report.get('item_level_items', 0)} | {display_metric(report.get('title_completeness'))} | "
            f"{display_metric(report.get('date_completeness'))} | {display_metric(report.get('evidence_completeness'))} | "
            f"{'是' if report.get('page_level_fallback') else '否'} |"
        )

    sections = [
        "### 抽取概览\n\n" + "\n".join(overview),
        "### 详情解析情况\n\n" + render_detail_parsing_overview(item_report),
        "### 详情失败概览\n\n" + render_detail_failure_overview(item_report),
        "### 本周新增或变化条目\n\n" + render_changed_items_summary(source_items),
    ]
    if baseline_count:
        baseline_items = [item for item in source_items if item.get("record_scope") == "item" and item.get("change_status") == "baseline"][:5]
        baseline_rows = ["| 来源 | 标题 | 日期文本 | 质量 | 官方链接 |", "|---|---|---|---|---|"]
        for item in baseline_items:
            baseline_rows.append(
                f"| {escape_table_cell(item.get('source_name'))} | {escape_table_cell(item.get('title'))} | "
                f"{escape_table_cell(item.get('date_text') or item.get('published_date_text') or '未知')} | "
                f"{escape_table_cell(item.get('source_quality'))} | {format_link(item.get('url'))} |"
            )
        sections.append(
            "### 首次采集基线\n\n"
            "本次为条目级解析器首次成功运行，发现的既有官方条目被标记为 baseline。"
            "baseline 仅表示建立采集基线，不代表这些内容在本周发布。\n\n"
            + "\n".join(baseline_rows)
        )
    sections.append("### 条目抽取质量\n\n" + "\n".join(quality_rows))
    reused_count = sum(
        int(report.get("reused_previous_success") or 0)
        for report in reports
        if isinstance(report, dict)
    )
    if reused_count:
        sections.append(
            "### 历史有效记录复用\n\n"
            "本轮部分详情页重新获取失败，系统保留最近一次成功解析的结构化记录。"
            "复用记录不代表本轮重新确认，也不计为新增或内容变化。"
        )
    return "\n\n".join(sections)


def render_official_item_diagnostics(source_items: list[dict[str, object]], item_report: dict[str, object]) -> str:
    item_records = [item for item in source_items if item.get("record_scope") == "item"]
    if not item_records:
        item_table = "当前仅形成页面级 fallback，没有达到条目级证据门槛的记录。"
    else:
        rows = [
            "| 状态 | 来源 | 标题 | 日期文本 | 相关性 | 层级 | 质量 | 字段证据 | 官方链接 |",
            "|---|---|---|---|---|---|---|---|---|",
        ]
        for item in item_records:
            field_evidence = item.get("field_evidence") or {}
            rows.append(
                "| "
                + " | ".join(
                    [
                        escape_table_cell(item.get("change_status")),
                        escape_table_cell(item.get("source_name")),
                        escape_table_cell(item.get("title")),
                        escape_table_cell(item.get("date_text") or item.get("published_date_text") or "未知"),
                        escape_table_cell(item.get("starlink_relevance")),
                        escape_table_cell(item.get("extracted_level")),
                        f"{escape_table_cell(item.get('source_quality'))}/{escape_table_cell(item.get('extraction_confidence'))}",
                        escape_table_cell(", ".join(sorted(field_evidence)) if isinstance(field_evidence, dict) else ""),
                        format_link(item.get("url")),
                    ]
                )
                + " |"
            )
        item_table = "\n".join(rows)
    return render_official_item_quality_table(item_report) + "\n\n" + item_table


def render_page_change_notes(source_statuses: dict[str, dict[str, object]]) -> str:
    if not source_statuses:
        return "本次没有页面级变化检测记录。"
    rows: list[str] = []
    for source_id, status in source_statuses.items():
        source_name = status.get("source_name", source_id)
        page_change = status.get("change_status", "unknown")
        new_items = int(status.get("new_items") or 0)
        changed_items = int(status.get("changed_items") or 0)
        if new_items or changed_items:
            explanation = "当前规则检测到新增或内容变化条目，仍需结合来源链接人工复核。"
        elif page_change == "changed":
            explanation = "页面级 hash 发生变化，但当前规则未检测到可确认的新增或内容变化条目。"
        elif page_change == "unchanged":
            explanation = "页面级 hash 未发生变化，当前规则也未检测到新增或内容变化条目。"
        else:
            explanation = "页面级变化状态暂不明确，当前规则未检测到可确认的新增或内容变化条目。"
        rows.append(f"- {source_name}：{explanation}")
    rows.append("页面变化状态与条目变化状态是两个检测层级，不能相互替代。")
    return "\n".join(rows)


def load_json_for_report(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def apply_item_report_to_meta(meta: dict[str, str], item_report: dict[str, object]) -> None:
    sources = item_report.get("sources", {}) if isinstance(item_report, dict) else {}
    reports = list(sources.values()) if isinstance(sources, dict) else []
    reports = [report for report in reports if isinstance(report, dict)]
    baseline = sum(int(report.get("baseline_items") or 0) for report in reports)
    item_level = sum(int(report.get("item_level_items") or 0) for report in reports)
    page_level = sum(int(report.get("page_level_items") or 0) for report in reports)
    meta["baseline_items"] = str(baseline)
    meta["item_level_items"] = str(item_level)
    meta["page_level_items"] = str(page_level)
    lines = [
        f"- {report.get('source_name') or report.get('source_id')}：静态候选 {report.get('static_candidate_count', 0)} / "
        f"渲染候选 {report.get('rendered_candidate_count', 0)} / "
        f"候选总数 {report.get('candidate_count_total', report.get('candidate_count', 0))} / "
        f"最终详情成功 {report.get('final_detail_success', report.get('detail_fetch_success', 0))} / "
        f"失败 {report.get('final_detail_failed', report.get('detail_fetch_failed', 0))} / "
        f"条目级 {report.get('item_level_items', 0)} / 页面级 {report.get('page_level_items', 0)} / "
        f"baseline {report.get('baseline_items', 0)} / fallback "
        f"{'是' if report.get('page_level_fallback') else '否'} / 直接 Starlink "
        f"{(report.get('relevance_counts') or {}).get('direct', 0) if isinstance(report.get('relevance_counts'), dict) else 0}"
        for report in reports
    ]
    if baseline:
        lines.append("本次为条目级解析首次建库，baseline 条目不等同于本周新增。")
    meta["item_extraction_overview"] = "\n".join(lines) if lines else "暂无官方条目抽取结果。"
    detail_lines: list[str] = []
    failure_lines: list[str] = []
    reused = 0
    for report in reports:
        rate = report.get("final_success_rate")
        rate_text = "unknown" if rate is None else f"{float(rate):.0%}"
        detail_lines.append(
            f"- {report.get('source_name') or report.get('source_id')}：静态候选 {report.get('static_candidate_count', 0)} / "
            f"渲染候选 {report.get('rendered_candidate_count', 0)} / "
            f"候选总数 {report.get('candidate_count_total', report.get('candidate_count', 0))} / "
            f"静态详情成功 {report.get('static_detail_success', 0)} / "
            f"渲染详情成功 {report.get('rendered_detail_success', 0)} / "
            f"最终详情成功 {report.get('final_detail_success', 0)} / "
            f"失败 {report.get('final_detail_failed', 0)} / 成功率 {rate_text}"
        )
        failure_types = report.get("failure_types", {})
        if isinstance(failure_types, dict):
            failure_lines.extend(f"- {error_type}：{count}" for error_type, count in sorted(failure_types.items()))
        reused += int(report.get("reused_previous_success") or 0)
    meta["detail_extraction_overview"] = "\n".join(detail_lines) if detail_lines else "暂无官方详情解析结果。"
    meta["detail_failure_overview"] = "\n".join(failure_lines) if failure_lines else "本轮没有详情解析失败。"
    meta["historical_reuse_note"] = (
        "本轮部分详情解析失败，系统保留最近一次成功的结构化记录。该记录不代表本轮重新确认。"
        if reused
        else ""
    )


def apply_llm_to_meta(meta: dict[str, str], audit: dict[str, object]) -> None:
    guardrails = audit.get("guardrails", {}) if isinstance(audit.get("guardrails"), dict) else {}
    errors = audit.get("errors", [])
    warnings = audit.get("warnings", [])
    usage = audit.get("usage", {}) if isinstance(audit.get("usage"), dict) else {}
    monitoring_context = audit.get("monitoring_context", [])
    meta["llm_enabled"] = str(bool(audit.get("llm_enabled"))).lower()
    meta["llm_provider"] = str(audit.get("llm_provider") or "unknown")
    meta["llm_status"] = str(audit.get("llm_status") or "unknown")
    meta["llm_summary_generated"] = str(bool(audit.get("summary_generated"))).lower()
    meta["llm_model"] = str(audit.get("model") or "未配置")
    meta["llm_base_url_label"] = str(audit.get("base_url_label") or "unknown")
    meta["llm_input_records"] = str(audit.get("input_records") or 0)
    meta["llm_input_records_before_dedup"] = str(audit.get("input_records_before_dedup") or 0)
    meta["llm_input_records_after_dedup"] = str(audit.get("input_records_after_dedup") or 0)
    meta["llm_duplicate_records_removed"] = str(audit.get("duplicate_records_removed") or 0)
    meta["llm_unique_source_urls"] = str(audit.get("unique_source_urls") or 0)
    meta["llm_raw_candidate_records"] = str(audit.get("raw_candidate_records") or audit.get("input_records_before_dedup") or 0)
    meta["llm_records_after_url_dedup"] = str(audit.get("records_after_url_dedup") or audit.get("input_records_after_dedup") or 0)
    meta["llm_final_core_input_records"] = str(audit.get("final_core_input_records") or audit.get("input_records") or 0)
    meta["llm_final_core_unique_urls"] = str(audit.get("final_core_unique_urls") or 0)
    meta["llm_reused_historical_records"] = str(audit.get("reused_historical_records") or 0)
    meta["llm_output_record_references_before_dedup"] = str(audit.get("output_record_references_before_dedup") or 0)
    meta["llm_output_record_references_after_dedup"] = str(audit.get("output_record_references_after_dedup") or 0)
    meta["llm_output_url_references_before_dedup"] = str(audit.get("output_url_references_before_dedup") or 0)
    meta["llm_output_url_references_after_dedup"] = str(audit.get("output_url_references_after_dedup") or 0)
    meta["llm_invalid_record_ids_removed"] = str(audit.get("invalid_record_ids_removed") or 0)
    meta["llm_invalid_urls_removed"] = str(audit.get("invalid_urls_removed") or 0)
    meta["llm_missing_record_ids_repaired"] = str(audit.get("missing_record_ids_repaired") or 0)
    meta["llm_missing_urls_repaired"] = str(audit.get("missing_urls_repaired") or 0)
    meta["llm_key_points_removed_without_sources"] = str(audit.get("key_points_removed_without_sources") or 0)
    meta["llm_reference_alignment_status"] = str(audit.get("reference_alignment_status") or "not_run")
    meta["llm_prompt_tokens"] = display_metric(usage.get("prompt_tokens"))
    meta["llm_completion_tokens"] = display_metric(usage.get("completion_tokens"))
    meta["llm_total_tokens"] = display_metric(usage.get("total_tokens"))
    meta["llm_latency_ms"] = display_metric(usage.get("latency_ms"))
    meta["llm_validation_status"] = str(audit.get("validation_status") or "unknown")
    meta["llm_reason"] = str(audit.get("reason") or "")
    meta["llm_audit_path"] = "data/llm_audit.json"
    meta["llm_summary_path"] = "data/llm_summaries.json"
    meta["llm_usage_path"] = "data/llm_usage.jsonl"
    meta["llm_strict_source"] = str(bool(guardrails.get("strict_source"))).lower()
    meta["llm_page_level_no_fact_expansion"] = str(bool(guardrails.get("page_level_no_fact_expansion"))).lower()
    meta["llm_errors"] = "；".join(str(error) for error in errors) if isinstance(errors, list) else ""
    meta["llm_warnings"] = "；".join(str(warning) for warning in warnings) if isinstance(warnings, list) else ""
    if bool(audit.get("llm_enabled")) and audit.get("llm_status") == "skipped_no_api_key":
        meta["llm_current_status_text"] = "当前自动化已请求启用 LLM，但未检测到对应 provider 的 API Key，因此本次自动跳过。"
    elif bool(audit.get("llm_enabled")):
        meta["llm_current_status_text"] = (
            "代码层面 LLM 默认关闭；当前自动化运行已显式启用 LLM。"
            "只有 API 调用成功且通过来源约束校验后，摘要才会展示。"
        )
    else:
        meta["llm_current_status_text"] = "代码层面 LLM 默认关闭；当前自动化运行未启用 LLM，因此不会调用外部模型。"
    if isinstance(monitoring_context, list) and monitoring_context:
        meta["llm_monitoring_overview"] = "\n".join(
            f"- {entry.get('source_name') or entry.get('source_id') or 'unknown'}：{entry.get('interpretation') or '暂无解释。'}"
            for entry in monitoring_context
            if isinstance(entry, dict)
        )


def render_llm_summary_section(meta: dict[str, str], llm_summary_data: dict[str, object]) -> str:
    lines = [
        "## 大模型辅助摘要",
        "",
        f"LLM Provider：{meta.get('llm_provider', 'unknown')}",
        f"模型：{meta.get('llm_model', '未配置')}",
        f"状态：{meta.get('llm_status', 'unknown')}",
        "",
        "说明：",
        f"- {meta.get('llm_current_status_text', '')}",
        "- 本节仅在显式启用 LLM 且通过来源约束校验后生成；",
        "- 未配置当前 provider 对应的 API Key 时会自动跳过；",
        "- 大模型摘要只基于 `data/items.jsonl` 等本地结构化来源数据；",
        "- 无来源不写结论；",
        "- 页面级记录不扩展成具体事实。",
        "",
        "### 输入与引用去重",
        "",
        "| 指标 | 数量 |",
        "|---|---:|",
        f"| 原始候选记录 | {meta.get('llm_raw_candidate_records', '0')} |",
        f"| URL 去重后记录 | {meta.get('llm_records_after_url_dedup', '0')} |",
        f"| 最终核心输入记录 | {meta.get('llm_final_core_input_records', '0')} |",
        f"| 最终核心唯一 URL | {meta.get('llm_final_core_unique_urls', '0')} |",
        f"| 复用历史记录 | {meta.get('llm_reused_historical_records', '0')} |",
        f"| 删除重复记录 | {meta.get('llm_duplicate_records_removed', '0')} |",
        f"| 唯一来源 URL | {meta.get('llm_unique_source_urls', '0')} |",
        f"| 输出 record ID 引用（前 / 后） | {meta.get('llm_output_record_references_before_dedup', '0')} / {meta.get('llm_output_record_references_after_dedup', '0')} |",
        f"| 输出 URL 引用（前 / 后） | {meta.get('llm_output_url_references_before_dedup', '0')} / {meta.get('llm_output_url_references_after_dedup', '0')} |",
        f"| 移除非法 record ID | {meta.get('llm_invalid_record_ids_removed', '0')} |",
        f"| 移除非法 URL | {meta.get('llm_invalid_urls_removed', '0')} |",
        f"| 补齐缺失 record ID | {meta.get('llm_missing_record_ids_repaired', '0')} |",
        f"| 补齐缺失 URL | {meta.get('llm_missing_urls_repaired', '0')} |",
        f"| 删除无来源要点 | {meta.get('llm_key_points_removed_without_sources', '0')} |",
        f"| 引用对齐状态 | {meta.get('llm_reference_alignment_status', 'not_run')} |",
        "",
        "### 页面级监测解释",
        "",
        meta.get("llm_monitoring_overview", "暂无页面级监测解释。"),
        "",
        "### LLM 调用统计",
        "",
        "| 指标 | 数值 |",
        "|---|---:|",
        f"| Prompt tokens | {meta.get('llm_prompt_tokens', 'unknown')} |",
        f"| Completion tokens | {meta.get('llm_completion_tokens', 'unknown')} |",
        f"| Total tokens | {meta.get('llm_total_tokens', 'unknown')} |",
        f"| API 调用耗时 | {meta.get('llm_latency_ms', 'unknown')} ms |",
        "",
    ]
    if meta.get("llm_status") != "generated":
        reason = meta.get("llm_reason") or "LLM 未生成摘要。"
        lines.extend(
            [
                f"跳过原因：{reason}",
                "",
                "当前主流程仍会继续生成周报、邮件、GitHub 提交和 Gitee 同步。",
                "",
            ]
        )
        return "\n".join(lines)

    summary = llm_summary_data.get("summary", {}) if isinstance(llm_summary_data.get("summary"), dict) else {}
    overall = str(summary.get("overall_summary") or summary.get("overall_summary_cn") or "LLM 摘要文件缺少总体摘要。")
    lines.extend(["### 总体摘要", "", overall, "", "### 来源约束要点", "", "| 要点 | 来源记录 | 来源链接 | 限制说明 |", "|---|---|---|---|"])
    key_points = summary.get("key_points", [])
    if isinstance(key_points, list) and key_points:
        for point in key_points:
            if not isinstance(point, dict):
                continue
            ids = "、".join(str(item) for item in point.get("source_record_ids", []) if item)
            urls = "<br>".join(str(item) for item in point.get("source_urls", []) if item)
            lines.append(
                "| "
                + " | ".join(
                    [
                        escape_table_cell(point.get("point", "")),
                        escape_table_cell(ids),
                        escape_table_cell(urls),
                        escape_table_cell(point.get("caveat", "")),
                    ]
                )
                + " |"
            )
    else:
        lines.append("| 无 | 无 | 无 | LLM 未生成可展示要点 |")
    lines.append("")
    return "\n".join(lines)


def render_llm_audit_section(meta: dict[str, str]) -> str:
    rows = [
        ("LLM 是否启用", meta.get("llm_enabled", "unknown")),
        ("LLM Provider", meta.get("llm_provider", "unknown")),
        ("LLM 状态", meta.get("llm_status", "unknown")),
        ("模型", meta.get("llm_model", "未配置")),
        ("Base URL 类型", meta.get("llm_base_url_label", "unknown")),
        ("输入记录数", meta.get("llm_input_records", "0")),
        ("去重前输入记录", meta.get("llm_input_records_before_dedup", "0")),
        ("去重后输入记录", meta.get("llm_input_records_after_dedup", "0")),
        ("删除重复记录", meta.get("llm_duplicate_records_removed", "0")),
        ("唯一来源 URL", meta.get("llm_unique_source_urls", "0")),
        ("原始候选记录", meta.get("llm_raw_candidate_records", "0")),
        ("URL 去重后记录", meta.get("llm_records_after_url_dedup", "0")),
        ("最终核心输入记录", meta.get("llm_final_core_input_records", "0")),
        ("最终核心唯一 URL", meta.get("llm_final_core_unique_urls", "0")),
        ("复用历史记录", meta.get("llm_reused_historical_records", "0")),
        ("输出 record ID 去重前数量", meta.get("llm_output_record_references_before_dedup", "0")),
        ("输出 record ID 去重后数量", meta.get("llm_output_record_references_after_dedup", "0")),
        ("输出 URL 去重前数量", meta.get("llm_output_url_references_before_dedup", "0")),
        ("输出 URL 去重后数量", meta.get("llm_output_url_references_after_dedup", "0")),
        ("移除非法 record ID", meta.get("llm_invalid_record_ids_removed", "0")),
        ("移除非法 URL", meta.get("llm_invalid_urls_removed", "0")),
        ("补齐缺失 record ID", meta.get("llm_missing_record_ids_repaired", "0")),
        ("补齐缺失 URL", meta.get("llm_missing_urls_repaired", "0")),
        ("删除无来源要点", meta.get("llm_key_points_removed_without_sources", "0")),
        ("引用对齐状态", meta.get("llm_reference_alignment_status", "not_run")),
        ("Prompt tokens", meta.get("llm_prompt_tokens", "unknown")),
        ("Completion tokens", meta.get("llm_completion_tokens", "unknown")),
        ("Total tokens", meta.get("llm_total_tokens", "unknown")),
        ("API 调用耗时", f"{meta.get('llm_latency_ms', 'unknown')} ms"),
        ("校验状态", meta.get("llm_validation_status", "unknown")),
        ("严格来源约束", meta.get("llm_strict_source", "unknown")),
        ("页面级记录禁止事实扩展", meta.get("llm_page_level_no_fact_expansion", "unknown")),
        ("审计文件", meta.get("llm_audit_path", "data/llm_audit.json")),
        ("摘要文件", meta.get("llm_summary_path", "data/llm_summaries.json")),
        ("用量记录", meta.get("llm_usage_path", "data/llm_usage.jsonl")),
    ]
    lines = [
        "## 大模型摘要审计",
        "",
        "| 字段 | 内容 |",
        "|---|---|",
    ]
    for label, value in rows:
        lines.append(f"| {escape_table_cell(label)} | {escape_table_cell(value)} |")
    lines.extend(["", "### 页面级监测解释", "", meta.get("llm_monitoring_overview", "暂无页面级监测解释。")])
    if meta.get("llm_reason"):
        lines.extend(["", f"- 原因：{meta['llm_reason']}"])
    if meta.get("llm_errors"):
        lines.extend(["", "### 错误类型", "", f"- {meta['llm_errors']}"])
    if meta.get("llm_warnings"):
        lines.extend(["", "### 警告类型", "", f"- {meta['llm_warnings']}"])
    lines.append("")
    return "\n".join(lines)


def render_recent_run_summary(meta: dict[str, str]) -> str:
    return "\n".join(
        [
            f"- 运行时间：{meta.get('run_time', '未知')}",
            f"- ISO 周编号：{meta.get('iso_week', '未知')}",
            f"- 输出模式：{meta.get('output_mode', '未知')}",
            f"- 邮件发送方式：{meta.get('email_delivery_mode', 'unknown')}",
            f"- 报告生成时邮件状态：{meta.get('email_status_at_report', 'unknown')}",
            f"- 是否执行真实来源采集：{meta.get('collect_sources', '未知')}",
            f"- 是否生成解析质量诊断：{meta.get('quality_generated', '未知')}",
            f"- 已接入来源数量：{meta.get('connected_source_count', '未知')}",
            f"- 新增条目数：{meta.get('new_items', '未知')}",
            f"- 内容变化条目数：{meta.get('changed_items', '未知')}",
            f"- 未变化条目数：{meta.get('unchanged_items', '未知')}",
            f"- LLM Provider：{meta.get('llm_provider', 'unknown')}",
            f"- LLM 摘要状态：{meta.get('llm_status', 'unknown')}",
        ]
    )


def render_history_records(records: list[dict[str, str]]) -> str:
    rendered: list[str] = []
    for record in records:
        rendered.append(
            "\n".join(
                [
                    f"- 运行时间：{record.get('run_time', '未知')}",
                    f"  - ISO 周编号：{record.get('iso_week', '未知')}",
                    f"  - 执行环境：{record.get('environment', '未知')}",
                    f"  - Python 版本：{record.get('python_version', '未知')}",
                    f"  - 输出模式：{record.get('output_mode', '未知')}",
                    f"  - 邮件发送方式：{record.get('email_delivery_mode', '旧格式未记录独立邮件步骤')}",
                    f"  - 报告生成时邮件状态：{record.get('email_status_at_report', 'unknown')}",
                    f"  - 是否执行真实来源采集：{record.get('collect_sources', '未知')}",
                    f"  - 是否生成解析质量诊断：{record.get('quality_generated', '未知')}",
                    f"  - 页面变化状态：{record.get('page_change_status', '未知')}",
                    f"  - 已接入来源数量：{record.get('connected_source_count', '未知')}",
                ]
            )
        )
    return "\n".join(rendered)


def _split_base_and_history(existing: str) -> tuple[str, str]:
    candidates = []
    for heading in LEGACY_HISTORY_HEADINGS:
        index = existing.find(heading)
        if index != -1:
            candidates.append(index)

    if not candidates:
        return existing.rstrip(), ""

    first_history_index = min(candidates)
    return existing[:first_history_index].rstrip(), existing[first_history_index:]


def _parse_history_records(history_text: str) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    key_map = {
        "运行时间": "run_time",
        "追加时间": "run_time",
        "ISO 周编号": "iso_week",
        "执行环境": "environment",
        "Python 版本": "python_version",
        "输出模式": "output_mode",
        "是否发送邮件": "send_email",
        "邮件发送方式": "email_delivery_mode",
        "报告生成时邮件状态": "email_status_at_report",
        "是否执行真实来源采集": "collect_sources",
        "是否生成解析质量诊断": "quality_generated",
        "页面变化状态": "page_change_status",
        "已接入来源数量": "connected_source_count",
    }

    for raw_line in history_text.splitlines():
        stripped = raw_line.strip()
        if stripped.startswith("- 运行时间：") or stripped.startswith("- 追加时间："):
            if current:
                records.append(current)
            current = {}

        if not stripped.startswith("- "):
            continue

        content = stripped[2:]
        if "：" not in content:
            continue
        key, value = content.split("：", 1)
        normalized_key = key_map.get(key.strip())
        if current is not None and normalized_key:
            current[normalized_key] = value.strip()

    if current:
        records.append(current)

    return records


def load_existing_history(paths: list[Path]) -> list[dict[str, str]]:
    for path in paths:
        if not path.exists():
            continue
        _base, history_text = _split_base_and_history(path.read_text(encoding="utf-8"))
        records = _parse_history_records(history_text)
        if records:
            return records
    return []


def render_candidate_links(value: object) -> str:
    if not isinstance(value, list) or not value:
        return "[]"
    compact = []
    for candidate in value[:5]:
        if isinstance(candidate, dict):
            compact.append(
                {
                    "title": candidate.get("title", ""),
                    "url": candidate.get("url", ""),
                    "matched_keywords": candidate.get("matched_keywords", []),
                }
            )
    return escape_table_cell(json.dumps(compact, ensure_ascii=False))


def render_detail_item_table(item: dict[str, object]) -> str:
    rows = [
        ("id", item.get("id", "")),
        ("title", item.get("title", "")),
        ("url", item.get("url", "")),
        ("source_id", item.get("source_id", "")),
        ("category", item.get("category", "")),
        ("change_status", item.get("change_status", "")),
        ("extracted_level", item.get("extracted_level", "")),
        ("source_quality", item.get("source_quality", "")),
        ("extraction_confidence", item.get("extraction_confidence", "")),
        ("content_hash", item.get("content_hash", "")),
        ("previous_content_hash", item.get("previous_content_hash", "")),
        ("first_seen_at", item.get("first_seen_at", "")),
        ("last_seen_at", item.get("last_seen_at", "")),
        ("last_changed_at", item.get("last_changed_at", "")),
        ("matched_keywords", json.dumps(item.get("matched_keywords", []), ensure_ascii=False)),
        ("candidate_links", render_candidate_links(item.get("candidate_links"))),
        ("extraction_notes", item.get("extraction_notes", "")),
    ]
    output = ["| 字段 | 内容 |", "|---|---|"]
    for key, value in rows:
        output.append(f"| {escape_table_cell(key)} | {truncate_text(value, 700)} |")
    return "\n".join(output)


def render_detail_items(
    source_items: list[dict[str, object]],
    source_statuses: dict[str, dict[str, object]],
    max_source_items: int,
) -> str:
    grouped = group_items_by_source(source_items, max_source_items)
    sections: list[str] = []
    for index, (source_id, status) in enumerate(source_statuses.items(), start=1):
        source_name = escape_table_cell(status.get("source_name") or source_id)
        items = grouped.get(source_id, [])
        if not items:
            sections.append(f"### 6.{index} {source_name}\n\n本来源本次没有可展示条目。")
            continue
        item_sections = [render_detail_item_table(item) for item in items]
        sections.append(f"### 6.{index} {source_name}\n\n" + "\n\n".join(item_sections))

    for source_id, items in grouped.items():
        if source_id in source_statuses:
            continue
        source_name = escape_table_cell(items[0].get("source_name") if items else source_id)
        item_sections = [render_detail_item_table(item) for item in items]
        sections.append(f"### 6.{len(sections) + 1} {source_name}\n\n" + "\n\n".join(item_sections))

    return "\n\n".join(sections) if sections else "本次未采集到有效条目。"


def render_evidence_sections(source_items: list[dict[str, object]], max_source_items: int) -> str:
    if not source_items:
        return "本次没有可展示的摘要与证据片段。"
    sections: list[str] = []
    for index, item in enumerate(source_items[:max_source_items], start=1):
        sections.append(
            "\n".join(
                [
                    f"### 7.{index} {escape_table_cell(item.get('title', '未命名条目'))}",
                    "",
                    f"- 来源：{escape_table_cell(item.get('source_name', ''))}",
                    f"- 链接：{format_link(item.get('url'))}",
                    f"- summary：{truncate_text(item.get('summary', ''), 500)}",
                    f"- evidence：{truncate_text(item.get('evidence', ''), 500)}",
                ]
            )
        )
    return "\n\n".join(sections)


def apply_lifecycle_to_meta(meta: dict[str, str], lifecycle_report: dict[str, object]) -> None:
    totals = lifecycle_report.get("totals", {}) if isinstance(lifecycle_report, dict) else {}
    totals = totals if isinstance(totals, dict) else {}
    attention = lifecycle_report.get("attention_items", []) if isinstance(lifecycle_report, dict) else []
    meta["lifecycle_initialized"] = str(totals.get("initialized") or 0)
    meta["lifecycle_new_items"] = str(totals.get("new") or 0)
    meta["lifecycle_changed_items"] = str(totals.get("changed") or 0)
    meta["lifecycle_extraction_improved"] = str(totals.get("extraction_improved") or 0)
    meta["lifecycle_temporarily_missing"] = str(totals.get("temporarily_missing") or 0)
    meta["lifecycle_long_absent"] = str(totals.get("long_absent") or 0)
    meta["lifecycle_fetch_failed"] = str(totals.get("detail_fetch_failed") or 0)
    meta["lifecycle_recovered"] = str(totals.get("recovered_after_failure") or 0)
    meta["lifecycle_reappeared"] = str(totals.get("reappeared") or 0)
    meta["lifecycle_attention_items"] = str(len(attention) if isinstance(attention, list) else 0)
    meta["lifecycle_new_semantic_versions"] = str(totals.get("new_semantic_versions") or 0)
    meta["lifecycle_new_extraction_revisions"] = str(totals.get("new_extraction_revisions") or 0)
    meta["lifecycle_event_count"] = str(totals.get("lifecycle_events") or 0)


def _lifecycle_events(report: dict[str, object], event_types: set[str] | None = None) -> list[dict[str, object]]:
    events = report.get("events_this_run", []) if isinstance(report, dict) else []
    if not isinstance(events, list):
        return []
    selected = [event for event in events if isinstance(event, dict)]
    if event_types is not None:
        selected = [event for event in selected if str(event.get("event_type")) in event_types]
    return selected


def _event_link(event: dict[str, object]) -> str:
    title = escape_table_cell(event.get("title") or event.get("record_id") or "未命名条目")
    url = str(event.get("canonical_url") or "")
    return f"[{title}]({url})" if url.startswith(("https://", "http://")) else title


def render_lifecycle_summary(report: dict[str, object]) -> str:
    sources = report.get("sources", {}) if isinstance(report, dict) else {}
    sources = sources if isinstance(sources, dict) else {}
    rows = [
        "| 来源 | Active | New | Changed | Extraction Improved | Temporarily Missing | Long Absent | Fetch Failed | Recovered | Reappeared |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    if sources:
        for source_id, source in sources.items():
            source = source if isinstance(source, dict) else {}
            rows.append(
                "| "
                + " | ".join(
                    [
                        escape_table_cell(source.get("source_name") or source_id),
                        str(source.get("active") or 0),
                        str(source.get("new") or 0),
                        str(source.get("changed") or 0),
                        str(source.get("extraction_improved") or 0),
                        str(source.get("temporarily_missing") or 0),
                        str(source.get("long_absent") or 0),
                        str(source.get("fetch_failed") or 0),
                        str(source.get("recovered") or 0),
                        str(source.get("reappeared") or 0),
                    ]
                )
                + " |"
            )
    else:
        rows.append("| 暂无 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |")

    events = _lifecycle_events(report)
    no_event_note = ""
    if not events:
        no_event_note = "\n\n本轮未产生新增、语义变化、暂时消失、连续失败或恢复事件。"

    new_events = _lifecycle_events(report, {"item_discovered"})
    new_text = "\n".join(
        f"- {_event_link(event)}：本轮首次发现，不自动等于官方本周首次发布。" for event in new_events
    ) or "本轮没有首次发现的新条目。"

    changed_events = _lifecycle_events(report, {"semantic_content_changed"})
    changed_lines: list[str] = []
    for event in changed_events:
        fields = "、".join(str(field) for field in event.get("changed_fields", [])[:8]) or "未列出"
        evidence = event.get("change_evidence", {})
        evidence = evidence if isinstance(evidence, dict) else {}
        snippets = []
        for field, pair in list(evidence.items())[:2]:
            pair = pair if isinstance(pair, dict) else {}
            snippets.append(
                f"{field}: {truncate_text(pair.get('before_excerpt') or '空', 90)} -> "
                f"{truncate_text(pair.get('after_excerpt') or '空', 90)}"
            )
        evidence_text = "；".join(snippets) or "已保存有限字段级证据"
        changed_lines.append(f"- {_event_link(event)}：变化字段 {fields}；{evidence_text}。")
    changed_text = "\n".join(changed_lines) or "本轮没有检测到语义内容变化。"

    improved_events = _lifecycle_events(report, {"extraction_improved"})
    improved_text = "\n".join(
        f"- {_event_link(event)}：{escape_table_cell('、'.join(str(field) for field in event.get('changed_fields', [])[:8]) or '解析字段更完整')}。"
        for event in improved_events
    ) or "本轮没有解析质量提升事件。"

    missing_events = _lifecycle_events(report, {"temporarily_missing", "long_absence_reached", "reappeared"})
    missing_text = "\n".join(
        f"- {_event_link(event)}：{event.get('event_type')}。" for event in missing_events
    ) or "本轮没有暂时消失、长期未见或重新出现事件。"

    fetch_events = _lifecycle_events(report, {"detail_fetch_failed", "detail_fetch_recovered"})
    fetch_text = "\n".join(
        f"- {_event_link(event)}：{event.get('event_type')}。" for event in fetch_events
    ) or "本轮没有详情抓取失败或恢复事件。"
    totals = report.get("totals", {}) if isinstance(report, dict) else {}
    totals = totals if isinstance(totals, dict) else {}

    return "\n".join(rows) + f"""{no_event_note}

### 本轮新增条目

{new_text}

### 本轮内容变化

{changed_text}

### 解析质量提升

以下变化仅表示解析完整度提升，不代表官方内容发生变化。

{improved_text}

### 暂时消失与长期未见

未在本轮索引中发现不代表官方删除。

{missing_text}

### 详情抓取失败与恢复

抓取失败或恢复属于采集链路状态，不代表官方业务状态。

{fetch_text}

### 历史版本

- 本轮新建 semantic versions：{totals.get("new_semantic_versions", 0)}
- 本轮新建 extraction revisions：{totals.get("new_extraction_revisions", 0)}
"""


def render_lifecycle_details(
    lifecycle_state: dict[str, object],
    lifecycle_report: dict[str, object],
    item_versions: list[dict[str, object]],
) -> str:
    states = lifecycle_state.get("items", {}) if isinstance(lifecycle_state, dict) else {}
    states = states if isinstance(states, dict) else {}
    state_rows = [
        "| Record ID | 来源 | 标题 | 当前状态 | Change status | Extraction status | Semantic version | Extraction revision | Missing count | Failure count | Attention | 官方 URL |",
        "|---|---|---|---|---|---|---:|---:|---:|---:|---|---|",
    ]
    for record_id, state in sorted(states.items(), key=lambda item: (str(item[1].get("source_id")), item[0])):
        state = state if isinstance(state, dict) else {}
        current_item = next(
            (
                item
                for item in item_versions[::-1]
                if item.get("record_id") == record_id
            ),
            {},
        )
        state_rows.append(
            "| "
            + " | ".join(
                [
                    escape_table_cell(record_id),
                    escape_table_cell(state.get("source_id", "")),
                    escape_table_cell(state.get("title") or current_item.get("title") or ""),
                    escape_table_cell(state.get("lifecycle_state", "")),
                    escape_table_cell(state.get("change_status", "unchanged")),
                    escape_table_cell(state.get("extraction_change_status", "unchanged")),
                    str(state.get("semantic_version") or 0),
                    str(state.get("extraction_revision") or 0),
                    str(state.get("consecutive_missing_observations") or 0),
                    str(state.get("consecutive_detail_failures") or 0),
                    "是" if state.get("attention_required") else "否",
                    format_link(state.get("canonical_url")),
                ]
            )
            + " |"
        )
    if len(state_rows) == 2:
        state_rows.append("| 暂无 |  |  |  |  |  | 0 | 0 | 0 | 0 | 否 |  |")

    event_rows = [
        "| 事件 | 来源 | 条目 | 前一状态 | 当前状态 | 变化字段 | 发生时间 | 限制说明 |",
        "|---|---|---|---|---|---|---|---|",
    ]
    limitation = {
        "item_discovered": "本轮首次发现，不等于本周发布",
        "semantic_content_changed": "仅表示结构化官方内容变化",
        "extraction_improved": "仅表示解析提升，不是事实变化",
        "temporarily_missing": "未判定删除",
        "long_absence_reached": "长期未见，不代表删除",
        "detail_fetch_failed": "采集失败，保留历史数据",
        "detail_fetch_recovered": "采集恢复，不是服务恢复",
        "reappeared": "重新出现，不是重新发布",
        "extraction_degraded": "解析完整度下降",
    }
    for event in _lifecycle_events(lifecycle_report):
        event_type = str(event.get("event_type") or "")
        event_rows.append(
            "| "
            + " | ".join(
                [
                    escape_table_cell(event_type),
                    escape_table_cell(event.get("source_name") or event.get("source_id") or ""),
                    _event_link(event),
                    escape_table_cell(event.get("previous_lifecycle_state", "")),
                    escape_table_cell(event.get("current_lifecycle_state", "")),
                    escape_table_cell("、".join(str(field) for field in event.get("changed_fields", [])[:8]) or "无"),
                    escape_table_cell(event.get("occurred_at", "")),
                    escape_table_cell(limitation.get(event_type, "采集系统内部事件")),
                ]
            )
            + " |"
        )
    if len(event_rows) == 2:
        event_rows.append("| 无 |  |  |  |  |  |  | 本轮没有需展示的生命周期事件 |")

    version_rows = [
        "| Record ID | Semantic version | Extraction revision | Version kind | Observed at | Changed fields |",
        "|---|---:|---:|---|---|---|",
    ]
    for version in item_versions:
        version_rows.append(
            "| "
            + " | ".join(
                [
                    escape_table_cell(version.get("record_id", "")),
                    str(version.get("semantic_version") or 0),
                    str(version.get("extraction_revision") or 0),
                    escape_table_cell(version.get("version_kind", "")),
                    escape_table_cell(version.get("observed_at", "")),
                    escape_table_cell("、".join(str(field) for field in version.get("changed_fields", [])[:8]) or "无"),
                ]
            )
            + " |"
        )
    if len(version_rows) == 2:
        version_rows.append("| 暂无 | 0 | 0 |  |  |  |")

    return f"""## 条目生命周期状态

{chr(10).join(state_rows)}

## 本轮生命周期事件

{chr(10).join(event_rows)}

## 结构化版本历史

{chr(10).join(version_rows)}
"""


def apply_operational_to_meta(
    meta: dict[str, str], alert_report: dict[str, object], run_health: dict[str, object]
) -> None:
    totals = alert_report.get("totals", {}) if isinstance(alert_report, dict) else {}
    totals = totals if isinstance(totals, dict) else {}
    meta["overall_health"] = str(run_health.get("overall_health") or "unknown")
    meta["overall_alert_status"] = str(alert_report.get("overall_alert_status") or "unknown")
    meta["new_alerts"] = str(
        int(totals.get("new_notifications") or 0)
        + int(totals.get("opened") or 0)
        + int(totals.get("escalated") or 0)
    )
    meta["resolved_alerts"] = str(totals.get("resolved") or 0)
    meta["open_warning_alerts"] = str(totals.get("open_warning") or 0)
    meta["open_high_alerts"] = str(totals.get("open_high") or 0)
    meta["open_critical_alerts"] = str(totals.get("open_critical") or 0)


def render_run_health_and_alerts(
    run_health: dict[str, object], alert_report: dict[str, object]
) -> str:
    components = run_health.get("components", {}) if isinstance(run_health, dict) else {}
    components = components if isinstance(components, dict) else {}
    labels = {
        "source_collection": "来源采集",
        "candidate_discovery": "候选发现",
        "detail_extraction": "详情解析",
        "lifecycle": "生命周期处理",
        "llm": "LLM",
        "output_validation": "输出检查",
        "project_audit": "项目审计",
        "email": "邮件",
        "gitee_sync": "Gitee 同步",
        "workflow_core": "Workflow 核心流程",
    }
    rows = [
        "| 指标 | 状态 |",
        "|---|---|",
        f"| Health phase | {escape_table_cell(run_health.get('health_phase', 'unknown'))} |",
        f"| Is final | {escape_table_cell(run_health.get('is_final', False))} |",
        f"| 整体运行健康 | {escape_table_cell(run_health.get('overall_health', 'unknown'))} |",
    ]
    for key, label in labels.items():
        component = components.get(key, {}) if isinstance(components.get(key), dict) else {}
        status = component.get("status", "unknown")
        if key == "llm" and component.get("enabled") is False:
            status = "disabled"
        rows.append(f"| {label} | {escape_table_cell(status)} |")
    totals = alert_report.get("totals", {}) if isinstance(alert_report, dict) else {}
    totals = totals if isinstance(totals, dict) else {}
    summary = [
        f"- Info：{totals.get('info', 0)}",
        f"- Warning：{totals.get('warning', 0)}",
        f"- High：{totals.get('high', 0)}",
        f"- Critical：{totals.get('critical', 0)}",
        f"- Open conditions：{totals.get('open_conditions', 0)}",
        f"- Resolved：{totals.get('resolved', 0)}",
    ]
    meaningful = any(int(totals.get(key) or 0) for key in ("warning", "high", "critical", "open_conditions"))
    note = "" if meaningful else "\n本轮未产生需要人工处理的运维告警。"
    timing_note = (
        "\n\n本表是周报生成时点的 provisional 快照；pending_at_render_time 不是失败。"
        "运行结束后的最终状态以 GitHub Actions Summary 和 data/run_health.json 为准。"
    )
    return "\n".join(rows) + timing_note + "\n\n### 本轮告警摘要\n\n" + "\n".join(summary) + note + f"\n\n{SEVERITY_SAFETY_NOTE}"


def render_alert_details(alert_report: dict[str, object]) -> str:
    alerts = []
    for key in ("alerts_this_run", "open_alerts"):
        values = alert_report.get(key, []) if isinstance(alert_report, dict) else []
        if isinstance(values, list):
            alerts.extend(value for value in values if isinstance(value, dict))
    rows = [
        "| Alert Type | Kind | Severity | Action | Source | Record ID | Consecutive | First Opened | Last Observed | Status | Message |",
        "|---|---|---|---|---|---|---:|---|---|---|---|",
    ]
    seen: set[tuple[str, str, str]] = set()
    for alert in alerts[:40]:
        identity = (str(alert.get("alert_key")), str(alert.get("action")), str(alert.get("status")))
        if identity in seen:
            continue
        seen.add(identity)
        rows.append(
            "| "
            + " | ".join(
                [
                    escape_table_cell(alert.get("alert_type", "")),
                    escape_table_cell(alert.get("alert_kind", "condition")),
                    escape_table_cell(alert.get("severity", "unknown")),
                    escape_table_cell(alert.get("action", "current")),
                    escape_table_cell(alert.get("source_id", "")),
                    escape_table_cell(alert.get("record_id", "")),
                    str(alert.get("consecutive_observations") or 0),
                    escape_table_cell(alert.get("first_opened_at", "")),
                    escape_table_cell(alert.get("last_observed_at") or alert.get("occurred_at") or ""),
                    escape_table_cell(alert.get("status", "event")),
                    escape_table_cell(alert.get("message_code", "")),
                ]
            )
            + " |"
        )
    if len(rows) == 2:
        rows.append("| 无 |  | info |  |  |  | 0 |  |  | normal | 本轮无运维告警 |")
    return "\n".join(rows) + f"\n\n{SEVERITY_SAFETY_NOTE}"


def render_health_trends(history: list[dict[str, object]]) -> str:
    rows = [
        "本表只展示 final health；旧记录中无法还原的 step outcome 保留为 unknown。",
        "",
        "| 运行时间 | Phase | Overall health | 来源可达 | 详情成功率 | 新条目 | 变化条目 | 失败条目 | Open warning | Open high | LLM 状态 | 邮件状态 | Gitee 状态 |",
        "|---|---|---|---|---:|---:|---:|---:|---:|---:|---|---|---|",
    ]
    for record in history[-12:]:
        total = int(record.get("total_sources") or 0)
        rows.append(
            "| "
            + " | ".join(
                [
                    escape_table_cell(record.get("generated_at", "")),
                    escape_table_cell(record.get("health_phase", "final")),
                    escape_table_cell(record.get("overall_health", "unknown")),
                    f"{record.get('reachable_sources', 0)}/{total}",
                    display_metric(record.get("detail_success_rate")),
                    str(record.get("new_items") or 0),
                    str(record.get("changed_items") or 0),
                    str(record.get("fetch_failed") or 0),
                    str(record.get("open_warning") or 0),
                    str(record.get("open_high") or 0),
                    escape_table_cell(record.get("llm_status", "unknown")),
                    escape_table_cell(record.get("email_status", "unknown")),
                    escape_table_cell(record.get("gitee_status", "unknown")),
                ]
            )
            + " |"
        )
    if len(rows) == 4:
        rows.append("| 暂无 | final | unknown | 0/0 | unknown | 0 | 0 | 0 | 0 | 0 | unknown | unknown | unknown |")
    return "\n".join(rows)


def render_replay_acceptance(report: dict[str, object]) -> str:
    if not report:
        return "最近一次离线 replay 报告不存在。"
    return "\n".join(
        [
            f"- 场景数量：{report.get('scenario_count', 'unknown')}",
            f"- 通过数量：{report.get('passed', 'unknown')}",
            f"- 失败数量：{report.get('failed', 'unknown')}",
            f"- 网络访问：{report.get('network_accessed', 'unknown')}",
            f"- 生产文件修改：{report.get('production_files_modified', 'unknown')}",
        ]
    )


def build_weekly_summary_markdown(
    meta: dict[str, str],
    source_items: list[dict[str, object]],
    source_statuses: dict[str, dict[str, object]],
    quality_sources: dict[str, dict[str, object]],
    llm_summary_data: dict[str, object],
    item_report: dict[str, object],
    lifecycle_report: dict[str, object] | None = None,
    run_health: dict[str, object] | None = None,
    alert_report: dict[str, object] | None = None,
) -> str:
    week_id = meta["iso_week"]
    lifecycle_report = lifecycle_report or {}
    run_health = run_health or {}
    alert_report = alert_report or {}
    return f"""# Starlink 情报周报总结版：{week_id}

## 1. 本周概览

本周自动化流程已运行。当前系统接入两个官方来源：
- Starlink Official Updates
- SpaceX Official Launches

当前阶段为阶段 4D.2：周报统一展示生成时点的 provisional 健康快照与独立邮件步骤，运行结束后的 final 状态以 GitHub Actions Summary 和 `data/run_health.json` 为准；pending_at_render_time 不是失败。这些采集及告警状态不代表官方业务状态或事件重要程度。

## 2. 本周核心结论

- 本周接入来源数量：{meta["connected_source_count"]}
- 可达来源数量：{meta["reachable_source_count"]}
- 页面发生变化的来源数量：{meta["page_changed_source_count"]}
- baseline 条目数量：{meta["baseline_items"]}
- 新增条目数量：{meta["new_items"]}
- 内容变化条目数量：{meta["changed_items"]}
- 未变化条目数量：{meta["unchanged_items"]}
- 当前解析质量总体判断：{meta["overall_quality"]}

说明：本节统计结论由结构化采集结果确定性生成，不依赖大模型；后续“大模型辅助摘要”小节为单独的来源约束型摘要。

{render_llm_summary_section(meta, llm_summary_data)}

## 结构化官方条目

{render_structured_official_items(source_items, item_report)}

## 条目生命周期概览

{render_lifecycle_summary(lifecycle_report)}

## 运行健康与告警

{render_run_health_and_alerts(run_health, alert_report)}

## 3. 来源状态概览

{render_summary_source_status_table(source_statuses, quality_sources)}

## 4. 本周值得关注的信息

### 4.1 新增或变化条目

{render_changed_items_summary(source_items)}

### 4.2 页面级变化说明

{render_page_change_notes(source_statuses)}

## 5. 解析质量概览

{render_summary_quality_table(quality_sources, source_statuses)}

说明：解析质量只表示规则化抽取完整度，不表示事实重要性或事实可信度。

## 6. 人工复查建议

- 对 `new` 或 `changed` 条目，建议人工打开来源链接复核；
- 对 `page_level / low` 记录，不应直接当作具体情报事实；
- 当前阶段不编造发布时间、发射时间、任务状态、载荷数量或技术细节；
- {meta.get("llm_current_status_text", "代码层面 LLM 默认关闭；当前自动化运行未启用 LLM，因此不会调用外部模型。")}

## 7. 本周文档

- 明细版文档：`weekly/{week_id}-details.md`
- 兼容索引文档：`weekly/{week_id}.md`

## 8. 最近一次自动化运行摘要

{render_recent_run_summary(meta)}
"""


def build_weekly_details_markdown(
    meta: dict[str, str],
    source_items: list[dict[str, object]],
    collection_errors: list[str],
    source_statuses: dict[str, dict[str, object]],
    quality_sources: dict[str, dict[str, object]],
    history_records: list[dict[str, str]],
    item_report: dict[str, object],
    detail_diagnostics: dict[str, object],
    llm_audit: dict[str, object] | None = None,
    lifecycle_state: dict[str, object] | None = None,
    lifecycle_report: dict[str, object] | None = None,
    item_versions: list[dict[str, object]] | None = None,
    run_health: dict[str, object] | None = None,
    alert_report: dict[str, object] | None = None,
    health_history: list[dict[str, object]] | None = None,
    replay_report: dict[str, object] | None = None,
) -> str:
    error_note = ""
    if collection_errors:
        error_note = "\n\n采集提示：本次采集存在错误，脚本已优雅处理，未输出任何密钥。"
    week_id = meta["iso_week"]
    lifecycle_state = lifecycle_state or {}
    lifecycle_report = lifecycle_report or {}
    item_versions = item_versions or []
    run_health = run_health or {}
    alert_report = alert_report or {}
    health_history = health_history or []
    replay_report = replay_report or {}
    return f"""# Starlink 情报周报明细版：{week_id}

## 1. 文档说明

本明细版用于来源复查、结构化数据核验和知识库维护。页面级 hash 变化与条目级结构化变化分别展示；大模型辅助摘要独立受来源约束，不能替代确定性统计。{error_note}

## 2. 数据文件

| 文件 | 说明 |
|---|---|
| `data/items.jsonl` | 结构化采集条目 |
| `data/source_status.json` | 来源状态与变化检测 |
| `data/extraction_quality.json` | 解析质量诊断 |
| `data/item_extraction_state.json` | 条目 stable ID、baseline 与历史状态 |
| `data/item_extraction_report.json` | 本次官方条目发现与详情解析报告 |
| `data/detail_extraction_diagnostics.json` | 逐候选静态/渲染详情解析状态与有限错误类型 |
| `data/item_lifecycle_state.json` | item-level 条目当前生命周期状态 |
| `data/item_versions.jsonl` | 限长的结构化语义与解析版本历史 |
| `data/lifecycle_events.jsonl` | 限长、去重的生命周期事件历史 |
| `data/lifecycle_report.json` | 本轮生命周期统计、事件与版本摘要 |
| `data/lifecycle_replay_report.json` | 完全离线的 `.invalid` 虚构生命周期回放验收摘要 |
| `data/alert_state.json` | 告警 watermark、open conditions、冷却和去重状态 |
| `data/alert_events.jsonl` | 限长的告警 notify/open/update/escalate/resolve 历史 |
| `data/alert_report.json` | 本轮告警摘要 |
| `data/run_health.json` | 当前运行健康状态 |
| `data/run_health_history.jsonl` | 限长、按 run ID 去重的长期趋势历史 |
| `data/llm_audit.json` | 可选 LLM 摘要审计 |
| `data/llm_summaries.json` | 可选 LLM 摘要输出 |
| `data/llm_usage.jsonl` | 限长的 LLM 状态、token 与耗时记录 |

{render_llm_audit_section(meta)}

## 3. 来源状态诊断

{render_detail_source_status_table(source_statuses)}

## 4. 本周变化检测

{render_change_detection_table(source_statuses, detail=True)}

## 5. 解析质量诊断

{render_detail_quality_table(quality_sources, source_statuses)}

## 6. 采集条目明细

{render_detail_items(source_items, source_statuses, int(meta.get("max_source_items", "10")))}

## 7. 原始摘要与证据片段

{render_evidence_sections(source_items, int(meta.get("max_source_items", "10")))}

## 官方条目解析诊断

{render_official_item_diagnostics(source_items, item_report)}

## 官方详情页解析诊断

{render_detail_diagnostics_table(detail_diagnostics, int(meta.get("max_history_records", "20")))}

### 详情失败类型

{render_detail_failure_overview(item_report)}

{render_lifecycle_details(lifecycle_state, lifecycle_report, item_versions)}

## 运维告警明细

{render_alert_details(alert_report)}

## 长期运行趋势

{render_health_trends(health_history)}

## 离线生命周期回放验收

{render_replay_acceptance(replay_report)}

## 8. 局限性

- 当前仅接入两个官方来源；
- 静态候选为 0 时才会按 `auto` 模式尝试受控 Chromium 索引渲染；
- 浏览器不可用、候选为空或详情证据不足时会保留页面级 fallback；
- hash 变化不等于事实变化；
- 解析质量分数不代表事实重要性；
- 不编造发布时间、发射时间、任务状态、载荷数量或 Starlink 技术事实。

{DETAIL_HISTORY_HEADING}

{render_history_records(history_records)}
"""


def build_weekly_index_markdown(
    meta: dict[str, str],
    summary_path: Path,
    details_path: Path,
    include_extended_summary: bool = False,
    source_statuses: dict[str, dict[str, object]] | None = None,
    quality_sources: dict[str, dict[str, object]] | None = None,
) -> str:
    week_id = meta["iso_week"]
    extended = ""
    if include_extended_summary:
        extended = f"""

## 简要状态

{render_summary_source_status_table(source_statuses or {{}}, quality_sources or {{}})}
"""
    return f"""# Starlink 情报周报：{week_id}

本周周报已拆分为两个文档：

- [总结版](./{summary_path.name})
- [明细版](./{details_path.name})

说明：
- 总结版适合快速阅读；
- 明细版适合来源复查、结构化数据核验和后续知识库维护。
{extended}
## 最近一次自动化运行摘要

{render_recent_run_summary(meta)}
"""


def build_legacy_markdown(
    meta: dict[str, str],
    source_items: list[dict[str, object]],
    collection_errors: list[str],
    source_statuses: dict[str, dict[str, object]],
    quality_sources: dict[str, dict[str, object]],
    history_records: list[dict[str, str]],
    item_report: dict[str, object],
    detail_diagnostics: dict[str, object],
) -> str:
    # Legacy mode keeps the old single-file shape but rewrites bounded content instead of appending forever.
    return build_weekly_details_markdown(
        meta=meta,
        source_items=source_items,
        collection_errors=collection_errors,
        source_statuses=source_statuses,
        quality_sources=quality_sources,
        history_records=history_records,
        item_report=item_report,
        detail_diagnostics=detail_diagnostics,
    ).replace("Starlink 情报周报明细版", "Starlink 情报周报")


def write_text_file(path: Path, content: str, dry_run: bool) -> None:
    if dry_run:
        print(f"[dry-run] 不会写入：{path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")
    print(f"已写入：{path}")


def write_weekly_outputs(
    paths: dict[str, Path],
    meta: dict[str, str],
    dry_run: bool,
    output_mode: str,
    max_records: int,
    source_items: list[dict[str, object]],
    collection_errors: list[str],
    source_statuses: dict[str, dict[str, object]],
    quality_sources: dict[str, dict[str, object]],
    llm_summary_data: dict[str, object],
    llm_audit: dict[str, object],
    item_report: dict[str, object],
    detail_diagnostics: dict[str, object],
    lifecycle_state: dict[str, object],
    lifecycle_report: dict[str, object],
    item_versions: list[dict[str, object]],
    run_health: dict[str, object],
    alert_report: dict[str, object],
    health_history: list[dict[str, object]],
    replay_report: dict[str, object],
) -> None:
    history_records = load_existing_history([paths["details"], paths["index"]])
    history_records.append(meta)
    history_records = history_records[-max_records:]

    summary_content = build_weekly_summary_markdown(
        meta, source_items, source_statuses, quality_sources, llm_summary_data, item_report, lifecycle_report, run_health, alert_report
    )
    details_content = build_weekly_details_markdown(
        meta,
        source_items,
        collection_errors,
        source_statuses,
        quality_sources,
        history_records,
        item_report,
        detail_diagnostics,
        llm_audit,
        lifecycle_state,
        lifecycle_report,
        item_versions,
        run_health,
        alert_report,
        health_history,
        replay_report,
    )

    if output_mode in {"dual", "both"}:
        write_text_file(paths["summary"], summary_content, dry_run)
        write_text_file(paths["details"], details_content, dry_run)
        index_content = build_weekly_index_markdown(
            meta,
            paths["summary"],
            paths["details"],
            include_extended_summary=output_mode == "both",
            source_statuses=source_statuses,
            quality_sources=quality_sources,
        )
        write_text_file(paths["index"], index_content, dry_run)
    elif output_mode == "legacy":
        legacy_content = build_legacy_markdown(
            meta,
            source_items,
            collection_errors,
            source_statuses,
            quality_sources,
            history_records,
            item_report,
            detail_diagnostics,
        )
        write_text_file(paths["index"], legacy_content, dry_run)


def load_weekly_manifest(path: Path = WEEKLY_MANIFEST_FILE) -> dict[str, object]:
    if not path.exists():
        return {"generated_at": None, "weeks": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        print(f"周报 manifest 无法解析，将重新生成：{path}")
        return {"generated_at": None, "weeks": {}}
    if not isinstance(data, dict):
        return {"generated_at": None, "weeks": {}}
    if not isinstance(data.get("weeks"), dict):
        data["weeks"] = {}
    return data


def write_weekly_manifest(manifest: dict[str, object], path: Path = WEEKLY_MANIFEST_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    manifest["generated_at"] = now_iso()
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def summarize_current_week_outputs(
    meta: dict[str, str],
    paths: dict[str, Path],
    source_statuses: dict[str, dict[str, object]],
    quality_sources: dict[str, dict[str, object]],
) -> dict[str, object]:
    return {
        "week_id": meta["iso_week"],
        "summary_path": meta["summary_path"],
        "details_path": meta["details_path"],
        "index_path": meta["index_path"],
        "generated_at": meta.get("run_iso") or now_iso(),
        "sources_total": int(meta.get("connected_source_count") or 0),
        "reachable_sources": int(meta.get("reachable_source_count") or 0),
        "new_items": int(meta.get("new_items") or 0),
        "changed_items": int(meta.get("changed_items") or 0),
        "unchanged_items": int(meta.get("unchanged_items") or 0),
        "dominant_quality": dominant_quality_value(source_statuses, quality_sources),
        "dominant_extracted_level": dominant_extracted_level_value(source_statuses, quality_sources),
        "llm_enabled": meta.get("llm_enabled") == "true",
        "llm_provider": meta.get("llm_provider", "unknown"),
        "llm_status": meta.get("llm_status", "unknown"),
        "llm_model": meta.get("llm_model", "未配置"),
        "llm_base_url_label": meta.get("llm_base_url_label", "unknown"),
        "llm_summary_path": meta.get("llm_summary_path", "data/llm_summaries.json"),
        "llm_audit_path": meta.get("llm_audit_path", "data/llm_audit.json"),
        "llm_usage_path": meta.get("llm_usage_path", "data/llm_usage.jsonl"),
        "llm_input_records_before_dedup": int(meta.get("llm_input_records_before_dedup") or 0),
        "llm_input_records_after_dedup": int(meta.get("llm_input_records_after_dedup") or 0),
        "llm_unique_source_urls": int(meta.get("llm_unique_source_urls") or 0),
        "llm_total_tokens": optional_number(meta.get("llm_total_tokens")),
        "llm_latency_ms": optional_number(meta.get("llm_latency_ms")),
        "item_lifecycle_state_path": meta.get("item_lifecycle_state_path", "data/item_lifecycle_state.json"),
        "item_versions_path": meta.get("item_versions_path", "data/item_versions.jsonl"),
        "lifecycle_events_path": meta.get("lifecycle_events_path", "data/lifecycle_events.jsonl"),
        "lifecycle_report_path": meta.get("lifecycle_report_path", "data/lifecycle_report.json"),
        "lifecycle_new_items": int(meta.get("lifecycle_new_items") or 0),
        "lifecycle_changed_items": int(meta.get("lifecycle_changed_items") or 0),
        "lifecycle_extraction_improved": int(meta.get("lifecycle_extraction_improved") or 0),
        "lifecycle_temporarily_missing": int(meta.get("lifecycle_temporarily_missing") or 0),
        "lifecycle_long_absent": int(meta.get("lifecycle_long_absent") or 0),
        "lifecycle_fetch_failed": int(meta.get("lifecycle_fetch_failed") or 0),
        "lifecycle_recovered": int(meta.get("lifecycle_recovered") or 0),
        "lifecycle_reappeared": int(meta.get("lifecycle_reappeared") or 0),
        "lifecycle_attention_items": int(meta.get("lifecycle_attention_items") or 0),
        "lifecycle_new_semantic_versions": int(meta.get("lifecycle_new_semantic_versions") or 0),
        "lifecycle_new_extraction_revisions": int(meta.get("lifecycle_new_extraction_revisions") or 0),
        "lifecycle_event_count": int(meta.get("lifecycle_event_count") or 0),
        "lifecycle_replay_report_path": meta.get("lifecycle_replay_report_path"),
        "alert_state_path": meta.get("alert_state_path"),
        "alert_events_path": meta.get("alert_events_path"),
        "alert_report_path": meta.get("alert_report_path"),
        "run_health_path": meta.get("run_health_path"),
        "run_health_history_path": meta.get("run_health_history_path"),
        "overall_health": meta.get("overall_health", "unknown"),
        "overall_alert_status": meta.get("overall_alert_status", "unknown"),
        "new_alerts": int(meta.get("new_alerts") or 0),
        "resolved_alerts": int(meta.get("resolved_alerts") or 0),
        "open_warning_alerts": int(meta.get("open_warning_alerts") or 0),
        "open_high_alerts": int(meta.get("open_high_alerts") or 0),
        "open_critical_alerts": int(meta.get("open_critical_alerts") or 0),
        "summary_exists": paths["summary"].exists(),
        "details_exists": paths["details"].exists(),
        "index_exists": paths["index"].exists(),
    }


def update_weekly_manifest(
    meta: dict[str, str],
    paths: dict[str, Path],
    source_statuses: dict[str, dict[str, object]],
    quality_sources: dict[str, dict[str, object]],
    dry_run: bool,
) -> dict[str, object]:
    manifest = load_weekly_manifest()
    weeks = manifest.setdefault("weeks", {})
    if isinstance(weeks, dict):
        weeks[meta["iso_week"]] = summarize_current_week_outputs(meta, paths, source_statuses, quality_sources)
    if dry_run:
        print(f"[dry-run] 不会写入周报 manifest：{WEEKLY_MANIFEST_FILE}")
        return manifest
    write_weekly_manifest(manifest)
    print(f"已更新周报 manifest：{WEEKLY_MANIFEST_FILE}")
    return manifest


def build_weekly_archive_index(manifest: dict[str, object]) -> str:
    weeks = manifest.get("weeks", {}) if isinstance(manifest, dict) else {}
    rows = [
        "# Starlink 情报周报索引",
        "",
        "本索引由 `starlink_intel_weekly` 项目自动维护，用于汇总每周生成的 Starlink 情报周报文档。",
        "",
        "## 周报列表",
        "",
        "| ISO 周编号 | 总结版 | 明细版 | 兼容索引 | 最近运行时间 | 来源数 | 新增 | 变化 | 未变化 | 主导解析质量 |",
        "|---|---|---|---|---|---:|---:|---:|---:|---|",
    ]
    if isinstance(weeks, dict) and weeks:
        for week_id in sorted(weeks.keys(), reverse=True):
            record = weeks.get(week_id, {})
            if not isinstance(record, dict):
                continue
            summary_name = Path(str(record.get("summary_path", f"weekly/{week_id}-summary.md"))).name
            details_name = Path(str(record.get("details_path", f"weekly/{week_id}-details.md"))).name
            index_name = Path(str(record.get("index_path", f"weekly/{week_id}.md"))).name
            rows.append(
                "| "
                + " | ".join(
                    [
                        escape_table_cell(week_id),
                        f"[summary](./{summary_name})",
                        f"[details](./{details_name})",
                        f"[index](./{index_name})",
                        escape_table_cell(record.get("generated_at", "")),
                        escape_table_cell(record.get("sources_total", 0)),
                        escape_table_cell(record.get("new_items", 0)),
                        escape_table_cell(record.get("changed_items", 0)),
                        escape_table_cell(record.get("unchanged_items", 0)),
                        escape_table_cell(record.get("dominant_quality", "unknown")),
                    ]
                )
                + " |"
            )
    else:
        rows.append("| 暂无 |  |  |  |  | 0 | 0 | 0 | 0 | unknown |")

    rows.extend(
        [
            "",
            "## 说明",
            "",
            "- 总结版适合快速阅读和组会分享；",
            "- 明细版适合来源复查、结构化数据核验和知识库维护；",
            "- 兼容索引用于保持旧版路径可访问；",
            "- 页面变化状态基于 hash 检测，不等于事实变化；",
            "- 解析质量仅表示规则化抽取完整度，不表示事实重要性或事实可信度。",
            "",
        ]
    )
    return "\n".join(rows)


def update_weekly_archive_index(manifest: dict[str, object], dry_run: bool) -> None:
    if dry_run:
        print(f"[dry-run] 不会写入周报总索引：{WEEKLY_ARCHIVE_INDEX}")
        return
    WEEKLY_ARCHIVE_INDEX.parent.mkdir(parents=True, exist_ok=True)
    WEEKLY_ARCHIVE_INDEX.write_text(build_weekly_archive_index(manifest), encoding="utf-8", newline="\n")
    print(f"已更新周报总索引：{WEEKLY_ARCHIVE_INDEX}")


def load_run_history(path: Path = RUN_HISTORY_FILE) -> list[dict[str, object]]:
    if not path.exists():
        return []
    records: list[dict[str, object]] = []
    with path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                value = json.loads(stripped)
            except json.JSONDecodeError:
                print(f"跳过无法解析的 run_history 行：{path}:{line_number}")
                continue
            if isinstance(value, dict):
                records.append(value)
    return records


def write_run_history(records: list[dict[str, object]], path: Path = RUN_HISTORY_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as file:
        for record in records:
            file.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def make_run_id(meta: dict[str, str]) -> str:
    configured = str(os.getenv("RUN_ID") or "").strip()
    if configured:
        return configured
    return hashlib.sha256(f"{meta.get('iso_week')}|{meta.get('run_iso')}|{meta.get('output_mode')}".encode("utf-8")).hexdigest()[:16]


def append_run_history(
    meta: dict[str, str],
    source_statuses: dict[str, dict[str, object]],
    dry_run: bool,
    max_run_history: int,
) -> None:
    if dry_run:
        print(f"[dry-run] 不会追加运行历史：{RUN_HISTORY_FILE}")
        return
    failed_sources = sum(1 for status in source_statuses.values() if status.get("health_status") != "reachable")
    record = {
        "run_id": make_run_id(meta),
        "week_id": meta["iso_week"],
        "run_at": meta.get("run_iso") or now_iso(),
        "mode": meta.get("output_mode", "dual"),
        "dry_run": False,
        "email_enabled": meta.get("send_email") == "是",
        "email_delivery_mode": meta.get("email_delivery_mode", "unknown"),
        "email_status_at_report": meta.get("email_status_at_report", "unknown"),
        "collect_enabled": meta.get("collect_sources") == "是",
        "sources_total": int(meta.get("connected_source_count") or 0),
        "reachable_sources": int(meta.get("reachable_source_count") or 0),
        "failed_sources": failed_sources,
        "new_items": int(meta.get("new_items") or 0),
        "changed_items": int(meta.get("changed_items") or 0),
        "unchanged_items": int(meta.get("unchanged_items") or 0),
        "summary_path": meta["summary_path"],
        "details_path": meta["details_path"],
        "index_path": meta["index_path"],
        "weekly_archive_index_path": meta["weekly_archive_index_path"],
        "weekly_manifest_path": meta["weekly_manifest_path"],
        "quality_check_status": meta.get("quality_check_status", "skipped"),
        "llm_enabled": meta.get("llm_enabled") == "true",
        "llm_provider": meta.get("llm_provider", "unknown"),
        "llm_status": meta.get("llm_status", "unknown"),
        "llm_model": meta.get("llm_model", "未配置"),
        "llm_base_url_label": meta.get("llm_base_url_label", "unknown"),
        "llm_summary_generated": meta.get("llm_summary_generated") == "true",
        "llm_input_records_before_dedup": int(meta.get("llm_input_records_before_dedup") or 0),
        "llm_input_records_after_dedup": int(meta.get("llm_input_records_after_dedup") or 0),
        "llm_total_tokens": optional_number(meta.get("llm_total_tokens")),
        "llm_latency_ms": optional_number(meta.get("llm_latency_ms")),
        "lifecycle_initialized": int(meta.get("lifecycle_initialized") or 0),
        "lifecycle_new_items": int(meta.get("lifecycle_new_items") or 0),
        "lifecycle_changed_items": int(meta.get("lifecycle_changed_items") or 0),
        "lifecycle_extraction_improved": int(meta.get("lifecycle_extraction_improved") or 0),
        "lifecycle_temporarily_missing": int(meta.get("lifecycle_temporarily_missing") or 0),
        "lifecycle_long_absent": int(meta.get("lifecycle_long_absent") or 0),
        "lifecycle_fetch_failed": int(meta.get("lifecycle_fetch_failed") or 0),
        "lifecycle_recovered": int(meta.get("lifecycle_recovered") or 0),
        "lifecycle_reappeared": int(meta.get("lifecycle_reappeared") or 0),
        "lifecycle_attention_items": int(meta.get("lifecycle_attention_items") or 0),
        "lifecycle_new_semantic_versions": int(meta.get("lifecycle_new_semantic_versions") or 0),
        "lifecycle_new_extraction_revisions": int(meta.get("lifecycle_new_extraction_revisions") or 0),
        "lifecycle_event_count": int(meta.get("lifecycle_event_count") or 0),
        "overall_health": meta.get("overall_health", "unknown"),
        "overall_alert_status": meta.get("overall_alert_status", "unknown"),
        "new_alerts": int(meta.get("new_alerts") or 0),
        "resolved_alerts": int(meta.get("resolved_alerts") or 0),
        "open_warning_alerts": int(meta.get("open_warning_alerts") or 0),
        "open_high_alerts": int(meta.get("open_high_alerts") or 0),
        "open_critical_alerts": int(meta.get("open_critical_alerts") or 0),
        "notes": "输出质量检查由 scripts/check_outputs.py 执行；本记录不保存任何 Secrets。",
    }
    records = load_run_history()
    replaced = False
    for index, existing in enumerate(records):
        if str(existing.get("run_id") or "") == str(record["run_id"]):
            records[index] = record
            replaced = True
            break
    if not replaced:
        records.append(record)
    records = records[-max_run_history:]
    write_run_history(records)
    print(f"已按 run_id 更新运行历史：{RUN_HISTORY_FILE}")


def latest_items_for_report(max_source_items: int, source_statuses: dict[str, dict[str, object]] | None = None) -> list[dict[str, object]]:
    items = load_items(ITEMS_FILE)
    status_priority = {"new": 0, "changed": 1, "baseline": 2, "unchanged": 3}
    items = sorted(
        items,
        key=lambda item: status_priority.get(str(item.get("change_status") or ""), 4),
    )
    if not source_statuses:
        return items[:max_source_items]

    selected: list[dict[str, object]] = []
    for source_id in source_statuses:
        source_items = [
            item
            for item in items
            if item.get("source_id") == source_id and item.get("seen_in_current_index") is not False
        ]
        item_level = [item for item in source_items if item.get("record_scope") == "item"]
        if item_level:
            source_items = item_level
        selected.extend(source_items[:max_source_items])
    return selected


def load_statuses_for_report() -> dict[str, dict[str, object]]:
    status = load_source_status(SOURCE_STATUS_FILE)
    sources = status.get("sources", {})
    return sources if isinstance(sources, dict) else {}


def load_quality_for_report() -> dict[str, dict[str, object]]:
    return quality_sources_from_data(load_extraction_quality(EXTRACTION_QUALITY_FILE))


def build_quality_overview(
    quality_sources: dict[str, dict[str, object]],
    source_statuses: dict[str, dict[str, object]],
) -> str:
    if not quality_sources and not source_statuses:
        return "无"

    lines: list[str] = []
    ordered_ids = list(source_statuses.keys()) or list(quality_sources.keys())
    for source_id in ordered_ids:
        quality = quality_sources.get(source_id, {})
        status = source_statuses.get(source_id, {})
        source_name = quality.get("source_name") or status.get("source_name") or source_id
        level = quality.get("dominant_extracted_level") or status.get("dominant_extracted_level") or "unknown"
        source_quality = quality.get("dominant_source_quality") or status.get("dominant_source_quality") or "unknown"
        confidence = quality.get("average_confidence") or status.get("average_confidence") or 0
        static_candidates = quality.get("static_candidate_count") or status.get("static_candidate_count") or 0
        rendered_candidates = quality.get("rendered_candidate_count") or status.get("rendered_candidate_count") or 0
        total_candidates = quality.get("candidate_count_total") or status.get("candidate_count_total") or 0
        lines.append(
            f"- {source_name}：{level} / {source_quality} / 平均置信度 {confidence} / "
            f"静态候选 {static_candidates} / 渲染候选 {rendered_candidates} / 候选总数 {total_candidates}"
        )
    return "\n".join(lines)


def apply_status_to_meta(meta: dict[str, str], source_statuses: dict[str, dict[str, object]]) -> None:
    if not source_statuses:
        return

    meta["connected_source_count"] = str(len(source_statuses))
    meta["reachable_source_count"] = str(reachable_count(source_statuses))
    meta["page_changed_source_count"] = str(page_changed_count(source_statuses))
    meta["health_status"] = "；".join(
        f"{status.get('source_name', source_id)}={status.get('health_status', 'unknown')}"
        for source_id, status in source_statuses.items()
    )
    meta["page_change_status"] = "；".join(
        f"{status.get('source_name', source_id)}={status.get('change_status', 'unknown')}"
        for source_id, status in source_statuses.items()
    )
    meta["http_status"] = "；".join(
        f"{status.get('source_name', source_id)}={status.get('http_status', 'unknown')}"
        for source_id, status in source_statuses.items()
    )
    meta["last_checked_at"] = "；".join(
        f"{status.get('source_name', source_id)}={status.get('last_checked_at', '未知')}"
        for source_id, status in source_statuses.items()
    )
    meta["last_changed_at"] = "；".join(
        f"{status.get('source_name', source_id)}={status.get('last_changed_at', '未知')}"
        for source_id, status in source_statuses.items()
    )
    meta["new_items"] = str(sum(int(status.get("new_items") or 0) for status in source_statuses.values()))
    meta["changed_items"] = str(sum(int(status.get("changed_items") or 0) for status in source_statuses.values()))
    meta["unchanged_items"] = str(sum(int(status.get("unchanged_items") or 0) for status in source_statuses.values()))
    meta["baseline_items"] = str(sum(int(status.get("baseline_items") or 0) for status in source_statuses.values()))
    meta["source_overview"] = "\n".join(
        f"- {status.get('source_name', source_id)}：{status.get('health_status', 'unknown')} / "
        f"{status.get('change_status', 'unknown')} / baseline{status.get('baseline_items', 0)} / 新增{status.get('new_items', 0)} / "
        f"变化{status.get('changed_items', 0)} / 未变化{status.get('unchanged_items', 0)} / "
        f"解析{status.get('dominant_extracted_level', 'unknown')}:{status.get('dominant_source_quality', 'unknown')}"
        for source_id, status in source_statuses.items()
    )


def apply_quality_to_meta(
    meta: dict[str, str],
    quality_sources: dict[str, dict[str, object]],
    source_statuses: dict[str, dict[str, object]],
) -> None:
    meta["quality_generated"] = "是" if quality_sources or source_statuses else "否"
    meta["quality_overview"] = build_quality_overview(quality_sources, source_statuses)
    meta["overall_quality"] = overall_quality_label(source_statuses, quality_sources)


def ensure_connected_sources_section_text(existing: str) -> str:
    section = f"""{CONNECTED_SOURCES_HEADING}

| 来源 | 类型 | 可信度 | 地址 | 状态 |
|---|---|---|---|---|
| Starlink Official Updates | official | S | https://www.starlink.com/updates | 已接入 |
| SpaceX Official Launches | official | S | https://www.spacex.com/launches | 已接入 |
"""
    return replace_or_insert_section(existing, CONNECTED_SOURCES_HEADING, section, before_heading=SOURCE_CHANGE_HEADING)


def update_source_change_section_text(existing: str, source_statuses: dict[str, dict[str, object]] | None = None) -> str:
    rows = [
        "| 来源 | 最近检查时间 | 可达性 | 页面变化状态 | 最近变化时间 | 当前状态 |",
        "|---|---|---|---|---|---|",
    ]
    for status in (source_statuses or {}).values():
        health_status = str(status.get("health_status") or "unknown")
        current_status = "正常" if health_status == "reachable" else "异常"
        rows.append(
            "| "
            + " | ".join(
                [
                    escape_table_cell(status.get("source_name", "")),
                    escape_table_cell(status.get("last_checked_at", "未知")),
                    escape_table_cell(health_status),
                    escape_table_cell(status.get("change_status", "unknown")),
                    escape_table_cell(status.get("last_changed_at", "未知")),
                    current_status,
                ]
            )
            + " |"
        )

    section = f"{SOURCE_CHANGE_HEADING}\n\n" + "\n".join(rows) + "\n"
    return replace_or_insert_section(existing, SOURCE_CHANGE_HEADING, section, before_heading=QUALITY_HEADING)


def update_quality_section_text(
    existing: str,
    quality_sources: dict[str, dict[str, object]],
    source_statuses: dict[str, dict[str, object]],
) -> str:
    section = f"{QUALITY_HEADING}\n\n{render_summary_quality_table(quality_sources, source_statuses)}\n"
    return replace_or_insert_section(existing, QUALITY_HEADING, section, before_heading=OUTPUT_STRUCTURE_HEADING)


def update_output_structure_section_text(existing: str) -> str:
    section = f"""{OUTPUT_STRUCTURE_HEADING}

| 文档 | 用途 |
|---|---|
| `weekly/YYYY-WW-summary.md` | 总结版，适合快速阅读和组会分享 |
| `weekly/YYYY-WW-details.md` | 明细版，适合来源复查、结构化数据核验和知识库维护 |
| `weekly/YYYY-WW.md` | 兼容索引，指向总结版和明细版 |
"""
    return replace_or_insert_section(existing, OUTPUT_STRUCTURE_HEADING, section, before_heading="## 最近一次自动化运行记录")


def update_archive_section_text(existing: str) -> str:
    section = f"""{ARCHIVE_HEADING}

| 文件 | 用途 |
|---|---|
| `weekly/index.md` | 周报总索引 |
| `data/weekly_manifest.json` | 机器可读的周报输出清单 |
| `data/run_history.jsonl` | 自动化运行历史记录 |
| `scripts/check_outputs.py` | 周报输出质量检查脚本 |
"""
    return replace_or_insert_section(existing, ARCHIVE_HEADING, section, before_heading="## 最近一次自动化运行记录")


def update_llm_section_text(existing: str) -> str:
    existing = existing.replace(LEGACY_LLM_HEADING, LLM_HEADING)
    existing = existing.replace(LEGACY_LLM_HEADING_3B, LLM_HEADING)
    section = f"""{LLM_HEADING}

阶段 3C 保留 `openai` 与 `deepseek` provider，并新增 LLM 输入与输出引用去重、页面级与条目级变化分层解释，以及限长用量记录。LLM 仍默认关闭；缺少当前 provider 对应的 API Key 时会写入跳过审计且不阻断主流程。

| 文件 | 用途 |
|---|---|
| `scripts/llm_summarize.py` | 基于本地结构化数据生成受来源约束的可选 LLM 摘要 |
| `data/llm_audit.json` | 记录 LLM 是否启用、是否跳过、校验状态和 guardrails |
| `data/llm_summaries.json` | 仅在 LLM 启用且校验通过后保存摘要 |
| `data/llm_usage.jsonl` | 仅记录 provider、model、状态、去重计数、token 与调用耗时 |

约束：

- ChatGPT Plus 订阅不能直接作为 GitHub Actions 中的 OpenAI API 调用额度使用；
- provider、model、base URL 等非敏感配置使用 GitHub Variables；API Key 只使用 GitHub Secrets；
- 不得把任何 API Key 写入代码、文档或提交记录；
- LLM 摘要只基于 `data/items.jsonl` 等本地结构化来源数据；
- 无来源不写结论；
- 页面级记录不扩展成具体事实；
- 页面 changed 仅代表页面 hash 或内容变化，不能等同于条目 changed；
- `items.jsonl` 保留历史，LLM 输入才按 `source_id + normalized_url` 选择每组最新记录；
- 用量记录不保存费用、完整 prompt、完整 response 或 API Key；
- LLM 输出与原始采集数据分离。
- 本阶段不新增来源，不编造 Starlink 或 SpaceX 事实。
"""
    return replace_or_insert_section(existing, LLM_HEADING, section, before_heading="## 最近一次自动化运行记录")


def replace_or_insert_section(existing: str, heading: str, section: str, before_heading: str | None = None) -> str:
    if heading in existing:
        before, rest = existing.split(heading, 1)
        next_heading_index = rest.find("\n## ")
        if next_heading_index == -1:
            return before.rstrip() + "\n\n" + section + "\n"
        after = rest[next_heading_index + 1 :]
        return before.rstrip() + "\n\n" + section + "\n" + after

    if before_heading and before_heading in existing:
        before, after = existing.split(before_heading, 1)
        return before.rstrip() + "\n\n" + section + "\n" + before_heading + after

    separator = "\n\n" if existing.strip() else ""
    return existing.rstrip() + separator + section + "\n"


def ensure_knowledge_base_exists() -> None:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    if not KNOWLEDGE_BASE.exists():
        KNOWLEDGE_BASE.write_text(
            "# Starlink 技术情报长期知识库\n\n"
            "本文件用于记录 Starlink 技术情报的长期更新内容。\n\n"
            "当前阶段已接入两个官方来源：Starlink Official Updates 与 SpaceX Official Launches。采集方式为规则化网页抽取，并新增解析质量诊断；不包含大模型事实推理。\n",
            encoding="utf-8",
        )


def update_knowledge_base_text(
    existing: str,
    meta: dict[str, str],
    source_statuses: dict[str, dict[str, object]],
    quality_sources: dict[str, dict[str, object]],
) -> str:
    existing = existing.replace(
        "当前阶段仅用于验证自动化链路，尚未接入真实 Starlink 信息采集、大模型总结和知识库更新功能。",
        "当前阶段已接入两个官方来源：Starlink Official Updates 与 SpaceX Official Launches。采集方式为规则化网页抽取，并新增双文档周报输出；不包含大模型事实推理。",
    )
    existing = existing.replace(
        "当前阶段已接入两个官方来源：Starlink Official Updates 与 SpaceX Official Launches。采集方式为规则化网页抽取，并新增解析质量诊断；不包含大模型事实推理。",
        "当前阶段已接入两个官方来源：Starlink Official Updates 与 SpaceX Official Launches。采集方式为规则化网页抽取，并新增双文档周报输出；不包含大模型事实推理。",
    )
    existing = ensure_connected_sources_section_text(existing)
    existing = update_source_change_section_text(existing, source_statuses)
    existing = update_quality_section_text(existing, quality_sources, source_statuses)
    existing = update_output_structure_section_text(existing)
    existing = update_archive_section_text(existing)
    existing = update_llm_section_text(existing)
    heading = "## 最近一次自动化运行记录"
    new_section = f"""{heading}

- 运行时间：{meta["run_time"]}
- ISO 周编号：{meta["iso_week"]}
- 执行环境：{meta["environment"]}
- Python 版本：{meta["python_version"]}
- 输出模式：{meta["output_mode"]}
- 邮件发送方式：{meta["email_delivery_mode"]}
- 报告生成时邮件状态：{meta["email_status_at_report"]}
- 是否执行真实来源采集：{meta["collect_sources"]}
- 是否生成解析质量诊断：{meta["quality_generated"]}
- 总结版文档：{meta["summary_path"]}
- 明细版文档：{meta["details_path"]}
- 兼容索引文档：{meta["index_path"]}
- 周报总索引：{meta["weekly_archive_index_path"]}
- 周报 manifest：{meta["weekly_manifest_path"]}
- 运行历史：{meta["run_history_path"]}
- 本次采集来源名称：{meta["source_names"]}
- 本次采集条目数量：{meta["source_item_count"]}
- 已接入来源数量：{meta["connected_source_count"]}
- 来源可达性概览：{meta["health_status"]}
- 页面变化状态概览：{meta["page_change_status"]}
- 新增条目数：{meta["new_items"]}
- 内容变化条目数：{meta["changed_items"]}
- 未变化条目数：{meta["unchanged_items"]}
- LLM Provider：{meta["llm_provider"]}
- LLM 模型：{meta["llm_model"]}
- LLM 摘要状态：{meta["llm_status"]}
- LLM 输入记录（去重前 / 后）：{meta["llm_input_records_before_dedup"]} / {meta["llm_input_records_after_dedup"]}
- LLM 唯一来源 URL：{meta["llm_unique_source_urls"]}
- LLM Total tokens：{meta["llm_total_tokens"]}
- LLM API 调用耗时：{meta["llm_latency_ms"]} ms
"""

    if heading not in existing:
        separator = "\n\n" if existing.strip() else ""
        return existing.rstrip() + separator + new_section + "\n"

    before, rest = existing.split(heading, 1)
    next_heading_index = rest.find("\n## ")
    if next_heading_index == -1:
        return before.rstrip() + "\n\n" + new_section + "\n"

    after = rest[next_heading_index + 1 :]
    return before.rstrip() + "\n\n" + new_section + "\n" + after


def update_knowledge_base(
    meta: dict[str, str],
    dry_run: bool,
    source_statuses: dict[str, dict[str, object]],
    quality_sources: dict[str, dict[str, object]],
) -> None:
    print(f"将更新长期知识库：{KNOWLEDGE_BASE}")
    if dry_run:
        print("[dry-run] 不会实际更新长期知识库。")
        return

    ensure_knowledge_base_exists()
    existing = KNOWLEDGE_BASE.read_text(encoding="utf-8")
    updated = update_knowledge_base_text(existing, meta, source_statuses, quality_sources)
    KNOWLEDGE_BASE.write_text(updated, encoding="utf-8", newline="\n")
    print("已更新长期知识库最近一次自动化运行记录、解析质量诊断、周报输出结构和归档说明。")


def main() -> int:
    if os.getenv("PYTHON_DOTENV_DISABLED") != "1":
        load_dotenv(PROJECT_ROOT / ".env", override=False)
    config_warnings: list[str] = []
    parser = argparse.ArgumentParser(description="生成 Starlink 情报周报自动化测试文档。")
    parser.add_argument("--no-email", action="store_true", help="只生成 Markdown，不发送邮件。")
    parser.add_argument("--dry-run", action="store_true", help="打印将要执行的操作，不写文件、不发邮件。")
    parser.add_argument("--no-collect", action="store_true", help="不执行真实来源采集，只生成周报。")
    parser.add_argument(
        "--render-mode",
        choices=["auto", "never", "always"],
        default="auto",
        help="官方索引页受控渲染策略；默认 auto，仅在静态候选为 0 时启用。",
    )
    parser.add_argument(
        "--detail-render-mode",
        choices=["auto", "never", "always"],
        default=os.getenv("DETAIL_RENDER_MODE") or "auto",
        help="官方详情页受控渲染策略；默认 auto，仅在静态详情不足时启用。",
    )
    parser.add_argument(
        "--max-rendered-details-per-source",
        type=int,
        default=int(os.getenv("MAX_RENDERED_DETAILS_PER_SOURCE") or 10),
    )
    parser.add_argument("--detail-timeout-ms", type=int, default=int(os.getenv("DETAIL_TIMEOUT_MS") or 30_000))
    parser.add_argument("--detail-wait-ms", type=int, default=int(os.getenv("DETAIL_WAIT_MS") or 1_500))
    parser.add_argument("--detail-max-scrolls", type=int, default=int(os.getenv("DETAIL_MAX_SCROLLS") or 3))
    parser.add_argument("--detail-concurrency", type=int, default=int(os.getenv("DETAIL_CONCURRENCY") or 1))
    parser.add_argument(
        "--rebootstrap-source",
        choices=["starlink_official_updates", "spacex_official_launches"],
        help="仅在人工明确重建基线时使用；GitHub Actions 不使用该参数。",
    )
    parser.add_argument(
        "--output-mode",
        choices=["dual", "legacy", "both"],
        default="dual",
        help="输出模式：dual 生成总结版/明细版/索引；legacy 仅更新旧版文件；both 生成双文档并在索引中附带较完整摘要。",
    )
    parser.add_argument(
        "--max-history-records",
        type=int,
        default=20,
        help="明细版自动化测试记录最多保留的条数，默认 20。",
    )
    parser.add_argument(
        "--max-source-items",
        type=int,
        default=10,
        help="周报中每个来源最多展示的真实来源记录数，默认 10。",
    )
    parser.add_argument(
        "--max-run-history",
        type=int,
        default=200,
        help="data/run_history.jsonl 最多保留的运行记录条数，默认 200。",
    )
    parser.add_argument("--enable-llm", action="store_true", help="显式启用可选 LLM 摘要。")
    parser.add_argument(
        "--llm-provider",
        default=os.getenv("LLM_PROVIDER") or DEFAULT_PROVIDER,
        help="LLM provider；默认读取 LLM_PROVIDER，否则使用 deepseek。",
    )
    parser.add_argument("--llm-model", default=None, help="覆盖当前 provider 的模型名称。")
    parser.add_argument(
        "--deepseek-model",
        default=os.getenv("DEEPSEEK_MODEL") or DEFAULT_DEEPSEEK_MODEL,
        help="DeepSeek 模型；默认读取 DEEPSEEK_MODEL。",
    )
    parser.add_argument(
        "--deepseek-base-url",
        default=os.getenv("DEEPSEEK_BASE_URL") or DEFAULT_DEEPSEEK_BASE_URL,
        help="DeepSeek OpenAI-compatible API base URL。",
    )
    parser.add_argument("--llm-max-items", type=int, default=10, help="LLM 摘要最多处理的来源记录数，默认 10。")
    parser.add_argument(
        "--max-llm-usage-records",
        type=int,
        default=int(os.getenv("LLM_MAX_USAGE_RECORDS") or DEFAULT_MAX_USAGE_RECORDS),
        help="data/llm_usage.jsonl 最多保留的记录条数，默认 200。",
    )
    parser.add_argument("--fail-on-llm-error", action="store_true", help="LLM 调用或校验失败时阻断主流程。")
    parser.add_argument(
        "--long-absence-observation-threshold",
        type=int,
        default=safe_positive_int(
            os.getenv("LONG_ABSENCE_OBSERVATION_THRESHOLD"),
            DEFAULT_LONG_ABSENCE_OBSERVATION_THRESHOLD,
            "LONG_ABSENCE_OBSERVATION_THRESHOLD",
            config_warnings,
        ),
    )
    parser.add_argument(
        "--long-absence-min-days",
        type=int,
        default=safe_positive_int(
            os.getenv("LONG_ABSENCE_MIN_DAYS"),
            DEFAULT_LONG_ABSENCE_MIN_DAYS,
            "LONG_ABSENCE_MIN_DAYS",
            config_warnings,
        ),
    )
    parser.add_argument(
        "--detail-failure-attention-threshold",
        type=int,
        default=safe_positive_int(
            os.getenv("DETAIL_FAILURE_ATTENTION_THRESHOLD"),
            DEFAULT_DETAIL_FAILURE_ATTENTION_THRESHOLD,
            "DETAIL_FAILURE_ATTENTION_THRESHOLD",
            config_warnings,
        ),
    )
    parser.add_argument(
        "--max-item-versions-per-record",
        type=int,
        default=safe_positive_int(
            os.getenv("MAX_ITEM_VERSIONS_PER_RECORD"),
            DEFAULT_MAX_ITEM_VERSIONS_PER_RECORD,
            "MAX_ITEM_VERSIONS_PER_RECORD",
            config_warnings,
        ),
    )
    parser.add_argument(
        "--max-lifecycle-events",
        type=int,
        default=safe_positive_int(
            os.getenv("MAX_LIFECYCLE_EVENTS"),
            DEFAULT_MAX_LIFECYCLE_EVENTS,
            "MAX_LIFECYCLE_EVENTS",
            config_warnings,
        ),
    )
    parser.add_argument("--lifecycle-dry-run", action="store_true", help="仅构建生命周期更新计划，不写入生命周期文件。")
    args = parser.parse_args()

    for warning in config_warnings:
        print(f"warning: {warning}")

    if args.max_history_records < 1:
        print("--max-history-records 必须是大于等于 1 的整数。")
        return 2
    if args.max_source_items < 1:
        print("--max-source-items 必须是大于等于 1 的整数。")
        return 2
    if args.max_run_history < 1:
        print("--max-run-history 必须是大于等于 1 的整数。")
        return 2
    if args.llm_max_items < 1:
        print("--llm-max-items 必须是大于等于 1 的整数。")
        return 2
    if args.max_llm_usage_records < 1:
        print("--max-llm-usage-records 必须是大于等于 1 的整数。")
        return 2
    if args.max_rendered_details_per_source < 0 or args.detail_wait_ms < 0 or args.detail_max_scrolls < 0:
        print("详情渲染数量、等待时间和最大滚动次数不能小于 0。")
        return 2
    if args.detail_timeout_ms < 1 or args.detail_concurrency < 1:
        print("详情超时和并发参数必须大于等于 1。")
        return 2
    if min(
        args.long_absence_observation_threshold,
        args.long_absence_min_days,
        args.detail_failure_attention_threshold,
        args.max_item_versions_per_record,
        args.max_lifecycle_events,
    ) < 1:
        print("生命周期阈值必须是大于等于 1 的整数。")
        return 2

    send_email_enabled = not args.no_email and not args.dry_run
    collect_enabled = not args.no_collect
    meta = get_run_metadata(send_email_enabled, collect_enabled, args.output_mode)
    apply_email_reporting_mode(
        meta,
        send_email_enabled=send_email_enabled,
        no_email_requested=args.no_email,
        dry_run=args.dry_run,
        github_actions=os.getenv("GITHUB_ACTIONS", "").strip().lower() == "true",
    )
    paths = weekly_output_paths(meta["iso_week"])
    meta["summary_path"] = f"weekly/{paths['summary'].name}"
    meta["details_path"] = f"weekly/{paths['details'].name}"
    meta["index_path"] = f"weekly/{paths['index'].name}"

    collection_result = None
    collection_errors: list[str] = []
    source_items: list[dict[str, object]] = []
    source_statuses: dict[str, dict[str, object]] = {}
    quality_sources: dict[str, dict[str, object]] = {}
    item_report: dict[str, object] = {}
    detail_diagnostics: dict[str, object] = {}
    lifecycle_state: dict[str, object] = {}
    lifecycle_report: dict[str, object] = {}
    item_versions: list[dict[str, object]] = []
    alert_report: dict[str, object] = {}
    run_health: dict[str, object] = {}
    health_history: list[dict[str, object]] = []
    replay_report: dict[str, object] = load_json_for_report(LIFECYCLE_REPLAY_REPORT_FILE)

    print("开始执行 Starlink 情报周报自动化测试。")
    print(f"项目根目录：{PROJECT_ROOT}")
    print(f"当前 ISO 周编号：{meta['iso_week']}")
    print(f"输出模式：{args.output_mode}")
    print(f"邮件发送方式：{meta['email_delivery_mode']}")
    print(f"报告生成时邮件状态：{meta['email_status_at_report']}")
    print(f"是否执行真实来源采集：{meta['collect_sources']}")
    print("当前阶段：4D.2 最终状态展示统一与邮件报告回归修复。")
    print(f"是否启用 LLM 摘要：{'是' if args.enable_llm else '否'}")
    print(f"自动化测试记录最多保留：{args.max_history_records} 条")
    print(f"周报真实来源记录每个来源最多展示：{args.max_source_items} 条")
    meta["max_source_items"] = str(args.max_source_items)
    meta["max_history_records"] = str(args.max_history_records)

    if args.no_collect:
        print("已按 --no-collect 参数跳过真实来源采集。")
        source_statuses = load_statuses_for_report()
        quality_sources = load_quality_for_report()
        item_report = load_json_for_report(ITEM_EXTRACTION_REPORT_FILE)
        detail_diagnostics = load_json_for_report(DETAIL_EXTRACTION_DIAGNOSTICS_FILE)
        lifecycle_state = load_lifecycle_state()
        lifecycle_report = load_lifecycle_report()
        item_versions = load_lifecycle_jsonl(ITEM_VERSIONS_FILE)
        apply_status_to_meta(meta, source_statuses)
        apply_quality_to_meta(meta, quality_sources, source_statuses)
        apply_item_report_to_meta(meta, item_report)
        source_items = latest_items_for_report(args.max_source_items, source_statuses)
        meta["source_names"] = "、".join(str(status.get("source_name", source_id)) for source_id, status in source_statuses.items()) or "无"
        meta["source_item_count"] = str(len(source_items))
    else:
        print("开始采集真实来源：全部 enabled 官方来源。")
        collection_result = collect_all_sources(
            limit=args.max_source_items,
            dry_run=args.dry_run,
            save_raw=False,
            fail_on_error=False,
            render_mode=args.render_mode,
            detail_render_mode=args.detail_render_mode,
            max_rendered_details_per_source=args.max_rendered_details_per_source,
            detail_timeout_ms=args.detail_timeout_ms,
            detail_wait_ms=args.detail_wait_ms,
            detail_max_scrolls=args.detail_max_scrolls,
            detail_concurrency=args.detail_concurrency,
            bootstrap_mode="baseline",
            rebootstrap_source=args.rebootstrap_source,
            long_absence_observation_threshold=args.long_absence_observation_threshold,
            long_absence_min_days=args.long_absence_min_days,
            detail_failure_attention_threshold=args.detail_failure_attention_threshold,
            max_item_versions_per_record=args.max_item_versions_per_record,
            max_lifecycle_events=args.max_lifecycle_events,
            lifecycle_dry_run=args.lifecycle_dry_run,
        )
        collection_errors = collection_result.errors
        meta["source_names"] = "、".join(collection_result.sources) if collection_result.sources else "无"
        meta["source_item_count"] = str(len(collection_result.items))
        meta["new_items"] = str(collection_result.new_count)
        meta["changed_items"] = str(collection_result.changed_count)
        meta["unchanged_items"] = str(collection_result.unchanged_count)
        source_statuses = collection_result.source_statuses
        quality_sources = quality_sources_from_data(collection_result.extraction_quality)
        apply_status_to_meta(meta, source_statuses)
        apply_quality_to_meta(meta, quality_sources, source_statuses)
        item_report = collection_result.item_extraction_report
        detail_diagnostics = collection_result.detail_extraction_diagnostics
        lifecycle_state = collection_result.lifecycle_state
        lifecycle_report = collection_result.lifecycle_report
        item_versions = collection_result.lifecycle_versions
        apply_item_report_to_meta(meta, item_report)
        source_items = collection_result.items or latest_items_for_report(args.max_source_items, source_statuses)

    apply_lifecycle_to_meta(meta, lifecycle_report)

    llm_return_code, llm_audit = run_llm_summary(
        enabled=args.enable_llm,
        dry_run=args.dry_run,
        max_items=args.llm_max_items,
        max_usage_records=args.max_llm_usage_records,
        model=args.llm_model,
        provider=args.llm_provider,
        deepseek_model=args.deepseek_model,
        deepseek_base_url=args.deepseek_base_url,
        strict_source=True,
        fail_on_llm_error=args.fail_on_llm_error,
    )
    apply_llm_to_meta(meta, llm_audit)
    llm_summary_data = load_json_for_report(LLM_SUMMARY_FILE) if meta.get("llm_status") == "generated" else {}
    print(f"LLM Provider：{meta['llm_provider']}")
    print(f"LLM 模型：{meta['llm_model']}")
    print(f"LLM 摘要状态：{meta['llm_status']}")
    if llm_return_code != 0 and args.fail_on_llm_error:
        return llm_return_code

    operational_policy, operational_warnings = operational_policy_from_env()
    for warning in operational_warnings:
        print(f"warning: {warning}")
    operational_run_id = str(os.getenv("RUN_ID") or lifecycle_report.get("run_id") or make_run_id(meta))
    operational_started_at = str(os.getenv("RUN_STARTED_AT") or lifecycle_report.get("generated_at") or meta["run_iso"])
    lifecycle_event_history = load_operational_jsonl(LIFECYCLE_EVENTS_FILE)
    if collection_result is not None and (args.dry_run or args.lifecycle_dry_run):
        known_event_ids = {str(event.get("event_id")) for event in lifecycle_event_history}
        lifecycle_event_history.extend(
            event
            for event in collection_result.lifecycle_events
            if str(event.get("event_id")) not in known_event_ids
        )
    run_context = {
        "run_id": operational_run_id,
        "started_at": operational_started_at,
        "finished_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "health_phase": "provisional",
        "email_status": "pending_at_render_time",
        "gitee_status": "pending_at_render_time",
        "output_check_status": "pending_at_render_time",
        "project_audit_status": "pending_at_render_time",
        "core_run_status": "pending_at_render_time",
        "state_integrity_status": "passed" if lifecycle_state and lifecycle_report else "failed",
        "transaction_status": "passed",
        "stable_id_status": "passed",
    }
    alert_evaluation = evaluate_alerts_data(
        lifecycle_events=lifecycle_event_history,
        lifecycle_state=lifecycle_state,
        lifecycle_report=lifecycle_report,
        source_status={"sources": source_statuses},
        item_extraction_report=item_report,
        llm_audit=llm_audit,
        run_context=run_context,
        previous_state=load_operational_json(ALERT_STATE_FILE, default_alert_state()),
        existing_alert_events=load_operational_jsonl(ALERT_EVENTS_FILE),
        health_history=load_operational_jsonl(RUN_HEALTH_HISTORY_FILE),
        policy=operational_policy,
    )
    alert_report = alert_evaluation.report
    health_evaluation = build_run_health_data(
        source_status={"sources": source_statuses},
        item_extraction_report=item_report,
        lifecycle_report=lifecycle_report,
        llm_audit=llm_audit,
        alert_report=alert_report,
        run_context=run_context,
        previous_history=load_operational_jsonl(RUN_HEALTH_HISTORY_FILE),
        policy=operational_policy,
    )
    run_health = health_evaluation.health
    health_history = health_evaluation.history
    if not args.dry_run and not args.lifecycle_dry_run:
        write_health_evaluation(health_evaluation)
    apply_operational_to_meta(meta, alert_report, run_health)
    print(f"整体运行健康：{meta['overall_health']}")
    print(f"整体告警状态：{meta['overall_alert_status']}")

    write_weekly_outputs(
        paths=paths,
        meta=meta,
        dry_run=args.dry_run,
        output_mode=args.output_mode,
        max_records=args.max_history_records,
        source_items=source_items,
        collection_errors=collection_errors,
        source_statuses=source_statuses,
        quality_sources=quality_sources,
        llm_summary_data=llm_summary_data,
        llm_audit=llm_audit,
        item_report=item_report,
        detail_diagnostics=detail_diagnostics,
        lifecycle_state=lifecycle_state,
        lifecycle_report=lifecycle_report,
        item_versions=item_versions,
        run_health=run_health,
        alert_report=alert_report,
        health_history=health_history,
        replay_report=replay_report,
    )
    manifest = update_weekly_manifest(meta, paths, source_statuses, quality_sources, args.dry_run)
    update_weekly_archive_index(manifest, args.dry_run)
    append_run_history(meta, source_statuses, args.dry_run, args.max_run_history)
    update_knowledge_base(meta, args.dry_run, source_statuses, quality_sources)

    print(f"总结版文档：{meta['summary_path']}")
    print(f"明细版文档：{meta['details_path']}")
    print(f"兼容索引文档：{meta['index_path']}")
    print(f"周报总索引：{meta['weekly_archive_index_path']}")
    print(f"周报 manifest：{meta['weekly_manifest_path']}")
    print(f"运行历史：{meta['run_history_path']}")
    print(f"LLM 审计文件：{meta['llm_audit_path']}")
    print(f"LLM 摘要文件：{meta['llm_summary_path']}")
    print(f"LLM 用量记录：{meta['llm_usage_path']}")
    print(f"生命周期状态：{meta['item_lifecycle_state_path']}")
    print(f"生命周期报告：{meta['lifecycle_report_path']}")
    print(f"告警报告：{meta['alert_report_path']}")
    print(f"运行健康：{meta['run_health_path']}")

    if args.dry_run:
        print("[dry-run] 已完成演练，不会发送邮件。")
        return 0

    if args.no_email:
        print("已按 --no-email 参数跳过邮件发送。")
        return 0

    print("开始发送邮件。")
    health_components = run_health.get("components", {}) if isinstance(run_health, dict) else {}
    health_components = health_components if isinstance(health_components, dict) else {}
    alert_totals = alert_report.get("totals", {}) if isinstance(alert_report, dict) else {}
    alert_totals = alert_totals if isinstance(alert_totals, dict) else {}
    collection_context = {
        "stage": "4D.2",
        "collected": meta["collect_sources"],
        "source_names": meta["source_names"],
        "item_count": meta["source_item_count"],
        "health_status": meta["health_status"],
        "page_change_status": meta["page_change_status"],
        "new_items": meta["new_items"],
        "changed_items": meta["changed_items"],
        "unchanged_items": meta["unchanged_items"],
        "connected_source_count": meta["connected_source_count"],
        "source_overview": meta["source_overview"],
        "quality_overview": meta["quality_overview"],
        "quality_generated": meta["quality_generated"],
        "baseline_items": meta["baseline_items"],
        "item_level_items": meta["item_level_items"],
        "page_level_items": meta["page_level_items"],
        "item_extraction_overview": meta["item_extraction_overview"],
        "detail_extraction_overview": meta["detail_extraction_overview"],
        "detail_failure_overview": meta["detail_failure_overview"],
        "historical_reuse_note": meta["historical_reuse_note"],
        "lifecycle_new_items": meta["lifecycle_new_items"],
        "lifecycle_changed_items": meta["lifecycle_changed_items"],
        "lifecycle_extraction_improved": meta["lifecycle_extraction_improved"],
        "lifecycle_temporarily_missing": meta["lifecycle_temporarily_missing"],
        "lifecycle_long_absent": meta["lifecycle_long_absent"],
        "lifecycle_fetch_failed": meta["lifecycle_fetch_failed"],
        "lifecycle_recovered": meta["lifecycle_recovered"],
        "lifecycle_reappeared": meta["lifecycle_reappeared"],
        "lifecycle_attention_items": meta["lifecycle_attention_items"],
        "overall_health": meta["overall_health"],
        "overall_alert_status": meta["overall_alert_status"],
        "health_phase": str(run_health.get("health_phase") or "provisional"),
        "health_is_final": str(bool(run_health.get("is_final"))).lower(),
        "health_finalized_at": str(run_health.get("finalized_at") or "pending_at_render_time"),
        "health_timing_note": "运行结束后的最终状态以 GitHub Actions Summary 和 data/run_health.json 为准。",
        "health_source_collection": str((health_components.get("source_collection") or {}).get("status", "unknown")),
        "health_detail_extraction": str((health_components.get("detail_extraction") or {}).get("status", "unknown")),
        "health_lifecycle": str((health_components.get("lifecycle") or {}).get("status", "unknown")),
        "health_llm": str((health_components.get("llm") or {}).get("status", "unknown")),
        "health_output_validation": str((health_components.get("output_validation") or {}).get("status", "unknown")),
        "health_project_audit": str((health_components.get("project_audit") or {}).get("status", "unknown")),
        "health_email": str((health_components.get("email") or {}).get("status", "unknown")),
        "health_gitee_sync": str((health_components.get("gitee_sync") or {}).get("status", "unknown")),
        "alert_info": str(alert_totals.get("info") or 0),
        "alert_warning": str(alert_totals.get("warning") or 0),
        "alert_high": str(alert_totals.get("high") or 0),
        "alert_critical": str(alert_totals.get("critical") or 0),
        "alert_open_conditions": str(alert_totals.get("open_conditions") or 0),
        "resolved_alerts": str(alert_totals.get("resolved") or 0),
        "alert_empty_note": "本轮未产生需要人工处理的运维告警。" if not any(int(alert_totals.get(key) or 0) for key in ("warning", "high", "critical", "open_conditions")) else "",
        "summary_file": paths["summary"].name,
        "details_file": paths["details"].name,
        "index_file": paths["index"].name,
        "weekly_archive_index": "weekly/index.md",
        "llm_enabled": meta["llm_enabled"],
        "llm_provider": meta["llm_provider"],
        "llm_model": meta["llm_model"],
        "llm_base_url_label": meta["llm_base_url_label"],
        "llm_status": meta["llm_status"],
        "llm_reason": meta["llm_reason"],
        "llm_summary_generated": meta["llm_summary_generated"],
        "llm_input_records_before_dedup": meta["llm_input_records_before_dedup"],
        "llm_input_records_after_dedup": meta["llm_input_records_after_dedup"],
        "llm_duplicate_records_removed": meta["llm_duplicate_records_removed"],
        "llm_unique_source_urls": meta["llm_unique_source_urls"],
        "llm_raw_candidate_records": meta["llm_raw_candidate_records"],
        "llm_records_after_url_dedup": meta["llm_records_after_url_dedup"],
        "llm_final_core_input_records": meta["llm_final_core_input_records"],
        "llm_final_core_unique_urls": meta["llm_final_core_unique_urls"],
        "llm_reused_historical_records": meta["llm_reused_historical_records"],
        "llm_current_status_text": meta["llm_current_status_text"],
        "llm_prompt_tokens": meta["llm_prompt_tokens"],
        "llm_completion_tokens": meta["llm_completion_tokens"],
        "llm_total_tokens": meta["llm_total_tokens"],
        "llm_latency_ms": meta["llm_latency_ms"],
        "llm_monitoring_overview": meta["llm_monitoring_overview"],
    }
    if not send_weekly_email(
        paths["summary"],
        meta["iso_week"],
        collection_context=collection_context,
        attachment_paths=[paths["summary"], paths["details"]],
    ):
        return 1

    print("自动化测试流程执行完成。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
