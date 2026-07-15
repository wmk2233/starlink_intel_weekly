from __future__ import annotations

import argparse
import json
import os
import socket
import smtplib
import ssl
import sys
from email.message import EmailMessage
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"


def load_project_env() -> None:
    """Load local .env values when the file exists."""
    if os.getenv("PYTHON_DOTENV_DISABLED") != "1":
        load_dotenv(PROJECT_ROOT / ".env")


def _split_recipients(value: str) -> list[str]:
    normalized = value.replace(";", ",")
    return [item.strip() for item in normalized.split(",") if item.strip()]


def _get_config() -> tuple[dict[str, str], list[str]]:
    load_project_env()

    smtp_port = os.getenv("SMTP_PORT", "465").strip() or "465"
    mail_from = os.getenv("MAIL_FROM", "").strip() or os.getenv("SMTP_USER", "").strip()

    config = {
        "SMTP_HOST": os.getenv("SMTP_HOST", "").strip(),
        "SMTP_PORT": smtp_port,
        "SMTP_USER": os.getenv("SMTP_USER", "").strip(),
        "SMTP_PASSWORD": os.getenv("SMTP_PASSWORD", "").strip(),
        "MAIL_TO": os.getenv("MAIL_TO", "").strip(),
        "MAIL_FROM": mail_from,
    }

    required = ["SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD", "MAIL_TO"]
    missing = [name for name in required if not config[name]]
    return config, missing


def _read_json(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _step_health(value: object, *, critical: bool) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"success", "passed", "healthy"}:
        return "healthy"
    if normalized in {"failure", "failed", "cancelled", "canceled"}:
        return "unhealthy" if critical else "degraded"
    if normalized in {"skipped", "disabled", "not_applicable"}:
        return "not_applicable"
    return "pending_at_render_time"


def _source_map(payload: dict[str, object]) -> dict[str, dict[str, object]]:
    sources = payload.get("sources", {})
    if not isinstance(sources, dict):
        return {}
    return {str(source_id): value for source_id, value in sources.items() if isinstance(value, dict)}


def _rate_text(value: object) -> str:
    try:
        return f"{float(value):.0%}"
    except (TypeError, ValueError):
        return "unknown"


def _render_source_overview(sources: dict[str, dict[str, object]]) -> tuple[str, str]:
    lines: list[str] = []
    page_changes: list[str] = []
    for source_id, status in sorted(sources.items()):
        source_name = str(status.get("source_name") or source_id)
        reachable = status.get("reachable")
        reachability = "可达" if reachable is True else "不可达" if reachable is False else "unknown"
        change_status = str(status.get("change_status") or "unknown")
        page_changes.append(f"{source_name}={change_status}")
        lines.append(
            f"- {source_name}：可达性 {reachability} / 页面变化 {change_status} / "
            f"新增 {status.get('new_items', 0)} / 变化 {status.get('changed_items', 0)} / "
            f"未变化 {status.get('unchanged_items', 0)} / "
            f"解析层级 {status.get('dominant_extracted_level', 'unknown')} / "
            f"质量 {status.get('dominant_source_quality', 'unknown')}"
        )
    return "\n".join(lines) or "无来源状态结果。", "；".join(page_changes) or "unavailable"


def _render_item_extraction_overview(reports: dict[str, dict[str, object]]) -> str:
    lines: list[str] = []
    for source_id, report in sorted(reports.items()):
        source_name = str(report.get("source_name") or source_id)
        lines.append(
            f"- {source_name}：候选 {report.get('candidate_count_total', report.get('candidate_count', 0))} / "
            f"条目级 {report.get('item_level_items', 0)} / 页面级 {report.get('page_level_items', 0)} / "
            f"新增 {report.get('new_items', 0)} / 变化 {report.get('changed_items', 0)} / "
            f"未变化 {report.get('unchanged_items', 0)} / baseline {report.get('baseline_items', 0)} / "
            f"解析层级 {report.get('dominant_extracted_level', 'unknown')} / "
            f"质量 {report.get('dominant_source_quality', 'unknown')}"
        )
    return "\n".join(lines) if lines else "暂无官方条目抽取结果。"


def _render_detail_diagnostics(
    diagnostics: dict[str, dict[str, object]],
) -> tuple[str, str, int, int, int]:
    lines: list[str] = []
    failures: list[str] = []
    success_total = 0
    failed_total = 0
    reused_total = 0
    for source_id, report in sorted(diagnostics.items()):
        source_name = str(report.get("source_name") or source_id)
        success = int(report.get("final_success") or 0)
        failed = int(report.get("final_failed") or 0)
        reused = int(report.get("reused_previous_success") or 0)
        success_total += success
        failed_total += failed
        reused_total += reused
        lines.append(
            f"- {source_name}：候选 {report.get('candidate_count', 0)} / "
            f"静态成功 {report.get('static_success', 0)} / 渲染成功 {report.get('render_success', 0)} / "
            f"历史复用 {reused} / 最终成功 {success} / 失败 {failed} / "
            f"成功率 {_rate_text(report.get('success_rate'))}"
        )
        failure_types = report.get("failure_types", {})
        if isinstance(failure_types, dict):
            failures.extend(
                f"- {source_name} / {failure_type}：{count}"
                for failure_type, count in sorted(failure_types.items())
            )
    overview = "\n".join(lines) if lines else "暂无官方详情解析结果。"
    failure_overview = "\n".join(failures) if failures else "本轮没有详情解析失败。"
    return overview, failure_overview, success_total, failed_total, reused_total


def build_context_from_outputs(markdown_path: Path, week_id: str, details_path: Path | None = None) -> dict[str, str]:
    source_status = _read_json(DATA_DIR / "source_status.json")
    item_report = _read_json(DATA_DIR / "item_extraction_report.json")
    detail_diagnostics = _read_json(DATA_DIR / "detail_extraction_diagnostics.json")
    lifecycle = _read_json(DATA_DIR / "lifecycle_report.json")
    llm_audit = _read_json(DATA_DIR / "llm_audit.json")
    health = _read_json(DATA_DIR / "run_health.json")
    raw_alerts = _read_json(DATA_DIR / "alert_report.json")
    alerts = (
        raw_alerts
        if str(raw_alerts.get("run_id") or "") == str(health.get("run_id") or "")
        else {}
    )
    sources = _source_map(source_status)
    lifecycle_totals = lifecycle.get("totals", {}) if isinstance(lifecycle.get("totals"), dict) else {}
    alert_totals = alerts.get("totals", {}) if isinstance(alerts.get("totals"), dict) else {}
    llm_usage = llm_audit.get("usage", {}) if isinstance(llm_audit.get("usage"), dict) else {}
    components = health.get("components", {}) if isinstance(health.get("components"), dict) else {}
    item_sources = _source_map(item_report)
    detail_sources = _source_map(detail_diagnostics)

    def component_status(name: str) -> str:
        component = components.get(name, {}) if isinstance(components.get(name), dict) else {}
        return str(component.get("status") or "unknown")

    source_overview, page_change_status = _render_source_overview(sources)
    item_extraction_overview = _render_item_extraction_overview(item_sources)
    detail_extraction_overview, detail_failure_overview, detail_success, detail_failed, reused = _render_detail_diagnostics(detail_sources)
    item_new = sum(int(value.get("new_items") or 0) for value in item_sources.values())
    item_changed = sum(int(value.get("changed_items") or 0) for value in item_sources.values())
    item_unchanged = sum(int(value.get("unchanged_items") or 0) for value in item_sources.values())
    item_baseline = sum(int(value.get("baseline_items") or 0) for value in item_sources.values())
    item_level = sum(int(value.get("item_level_items") or 0) for value in item_sources.values())
    page_level = sum(int(value.get("page_level_items") or 0) for value in item_sources.values())
    item_count = sum(int(value.get("candidate_count_total", value.get("candidate_count", 0)) or 0) for value in item_sources.values())
    detail_total = detail_success + detail_failed
    context = {
        "stage": "4D.2",
        "collected": "是",
        "connected_source_count": str(len(sources)),
        "source_overview": source_overview,
        "quality_overview": (
            f"详情成功 {detail_success}，失败 {detail_failed}，成功率 "
            f"{_rate_text(detail_success / detail_total) if detail_total else 'unknown'}；"
            f"条目级 {item_level}，页面级 {page_level}"
        ),
        "quality_generated": "是" if item_report or detail_diagnostics else "否",
        "health_status": f"{sum(1 for value in sources.values() if isinstance(value, dict) and value.get('reachable') is True)}/{len(sources)} 来源可达",
        "page_change_status": page_change_status,
        "item_count": str(item_count),
        "new_items": str(item_new),
        "changed_items": str(item_changed),
        "unchanged_items": str(item_unchanged),
        "baseline_items": str(item_baseline),
        "item_level_items": str(item_level),
        "page_level_items": str(page_level),
        "item_extraction_overview": item_extraction_overview,
        "detail_extraction_overview": detail_extraction_overview,
        "detail_failure_overview": detail_failure_overview,
        "historical_reuse_note": (
            "本轮详情获取失败时复用了最近一次成功结构化记录；该记录不代表本轮重新确认。"
            if reused
            else ""
        ),
        "lifecycle_new_items": str(lifecycle_totals.get("new") or 0),
        "lifecycle_changed_items": str(lifecycle_totals.get("changed") or 0),
        "lifecycle_extraction_improved": str(lifecycle_totals.get("extraction_improved") or 0),
        "lifecycle_temporarily_missing": str(lifecycle_totals.get("temporarily_missing") or 0),
        "lifecycle_long_absent": str(lifecycle_totals.get("long_absent") or 0),
        "lifecycle_fetch_failed": str(lifecycle_totals.get("detail_fetch_failed") or 0),
        "lifecycle_recovered": str(lifecycle_totals.get("recovered") or 0),
        "lifecycle_reappeared": str(lifecycle_totals.get("reappeared") or 0),
        "lifecycle_attention_items": str(len(lifecycle.get("attention_items", []) or [])),
        "overall_health": str(health.get("overall_health") or "unknown"),
        "overall_alert_status": str(alerts.get("overall_alert_status") or "pending_at_render_time"),
        "health_phase": str(health.get("health_phase") or "provisional"),
        "health_is_final": str(bool(health.get("is_final"))).lower(),
        "health_finalized_at": str(health.get("finalized_at") or "pending_at_render_time"),
        "health_timing_note": "运行结束后的最终状态以 GitHub Actions Summary 和 data/run_health.json 为准。",
        "health_source_collection": component_status("source_collection"),
        "health_detail_extraction": component_status("detail_extraction"),
        "health_lifecycle": component_status("lifecycle"),
        "health_llm": component_status("llm"),
        "health_output_validation": _step_health(os.getenv("OUTPUT_CHECK_OUTCOME"), critical=True),
        "health_project_audit": _step_health(os.getenv("PROJECT_AUDIT_OUTCOME"), critical=True),
        "health_email": "pending_at_render_time",
        "health_gitee_sync": "pending_at_render_time",
        "alert_info": str(alert_totals.get("info") or 0),
        "alert_warning": str(alert_totals.get("warning") or 0),
        "alert_high": str(alert_totals.get("high") or 0),
        "alert_critical": str(alert_totals.get("critical") or 0),
        "alert_open_conditions": str(alert_totals.get("open_conditions") or 0),
        "resolved_alerts": str(alert_totals.get("resolved") or 0),
        "summary_file": markdown_path.name,
        "details_file": details_path.name if details_path else "未提供",
        "index_file": f"{week_id}.md",
        "weekly_archive_index": "weekly/index.md",
        "llm_enabled": str(bool(llm_audit.get("llm_enabled"))).lower(),
        "llm_provider": str(llm_audit.get("llm_provider") or llm_audit.get("provider") or "unknown"),
        "llm_model": str(llm_audit.get("model") or "未配置"),
        "llm_status": str(llm_audit.get("llm_status") or "unknown"),
        "llm_reason": str(llm_audit.get("reason") or "未知"),
        "llm_summary_generated": str(bool(llm_audit.get("summary_generated"))).lower(),
        "llm_current_status_text": "LLM 输出只基于允许的结构化官方记录。",
        "llm_raw_candidate_records": str(llm_audit.get("raw_candidate_records") or 0),
        "llm_records_after_url_dedup": str(llm_audit.get("records_after_url_dedup") or 0),
        "llm_final_core_input_records": str(llm_audit.get("final_core_input_records") or 0),
        "llm_final_core_unique_urls": str(llm_audit.get("final_core_unique_urls") or 0),
        "llm_reused_historical_records": str(llm_audit.get("reused_historical_records") or 0),
        "llm_prompt_tokens": str(llm_usage.get("prompt_tokens") or llm_audit.get("prompt_tokens") or "unknown"),
        "llm_completion_tokens": str(llm_usage.get("completion_tokens") or llm_audit.get("completion_tokens") or "unknown"),
        "llm_total_tokens": str(llm_usage.get("total_tokens") or llm_audit.get("total_tokens") or "unknown"),
        "llm_latency_ms": str(llm_usage.get("latency_ms") or llm_audit.get("latency_ms") or "unknown"),
        "llm_monitoring_overview": "运维健康不是官方事实来源。",
    }
    context["alert_empty_note"] = "本轮未产生需要人工处理的运维告警。" if not any(int(alert_totals.get(key) or 0) for key in ("warning", "high", "critical", "open_conditions")) else ""
    return context


def build_message(
    markdown_path: Path,
    week_id: str,
    config: dict[str, str],
    collection_context: dict[str, str] | None = None,
    attachment_paths: list[str | Path] | None = None,
) -> EmailMessage:
    markdown_text = markdown_path.read_text(encoding="utf-8")
    recipients = _split_recipients(config["MAIL_TO"])
    collection_context = collection_context or {}
    attachments = [Path(path) for path in (attachment_paths or [markdown_path])]

    message = EmailMessage()
    message["Subject"] = f"Starlink 情报周报自动化测试 - {week_id}"
    message["From"] = config["MAIL_FROM"]
    message["To"] = ", ".join(recipients)

    attachment_lines = "\n".join(f"- {path.name}" for path in attachments)
    try:
        baseline_count = int(collection_context.get("baseline_items", "0"))
    except (TypeError, ValueError):
        baseline_count = 0
    baseline_note = (
        "本次为条目级解析首次建库，baseline 条目不等同于本周新增。\n"
        if baseline_count > 0
        else ""
    )
    historical_reuse_note = collection_context.get("historical_reuse_note", "")
    if historical_reuse_note:
        historical_reuse_note = f"{historical_reuse_note}\n"
    body = (
        "本邮件由 starlink_intel_weekly 项目自动发送。\n"
        "当前阶段为阶段 4D.2：统一 final 状态展示，并恢复邮件中的来源、条目与详情诊断报告。\n"
        "原始事实与状态数据来自规则化网页采集、hash 变化检测和解析质量诊断。大模型仅对本地结构化来源数据进行受约束摘要，不使用外部知识，也不生成无来源事实。\n\n"
        "LLM 摘要状态：\n"
        f"- Provider：{collection_context.get('llm_provider', 'unknown')}\n"
        f"- 模型：{collection_context.get('llm_model', '未配置')}\n"
        f"- 是否启用：{collection_context.get('llm_enabled', 'false')}\n"
        f"- 当前状态：{collection_context.get('llm_status', 'unknown')}\n"
        f"- 摘要是否生成：{collection_context.get('llm_summary_generated', 'false')}\n"
        f"- 原因：{collection_context.get('llm_reason', '未知')}\n\n"
        f"{collection_context.get('llm_current_status_text', '')}\n\n"
        "LLM 输入与使用情况：\n"
        f"- 原始候选记录：{collection_context.get('llm_raw_candidate_records', '0')}\n"
        f"- URL 去重后记录：{collection_context.get('llm_records_after_url_dedup', '0')}\n"
        f"- 最终核心输入记录：{collection_context.get('llm_final_core_input_records', '0')}\n"
        f"- 最终核心唯一 URL：{collection_context.get('llm_final_core_unique_urls', '0')}\n"
        f"- 复用历史记录：{collection_context.get('llm_reused_historical_records', '0')}\n"
        f"- Prompt tokens：{collection_context.get('llm_prompt_tokens', 'unknown')}\n"
        f"- Completion tokens：{collection_context.get('llm_completion_tokens', 'unknown')}\n"
        f"- Total tokens：{collection_context.get('llm_total_tokens', 'unknown')}\n"
        f"- API 调用耗时：{collection_context.get('llm_latency_ms', 'unknown')} ms\n\n"
        "LLM 说明：\n"
        "- ChatGPT Plus 订阅不能直接作为 GitHub Actions 中的 OpenAI API 调用额度使用；\n"
        "- DeepSeek API Key 需要单独在 DeepSeek 平台获取；\n"
        "- 本地 API Key 只通过环境变量或 .env 提供，GitHub Actions API Key 只通过 GitHub Secrets 提供；\n"
        "- provider、model、base URL 等非敏感配置使用 GitHub Variables；\n"
        "- 未配置 API Key 时不会影响采集、周报、邮件、GitHub 和 Gitee 主流程。\n\n"
        "本周输出文档：\n"
        f"- 总结版：{collection_context.get('summary_file', markdown_path.name)}\n"
        f"- 明细版：{collection_context.get('details_file', '未生成')}\n"
        f"- 兼容索引：{collection_context.get('index_file', '未生成')}\n"
        f"- 周报总索引：{collection_context.get('weekly_archive_index', 'weekly/index.md')}\n\n"
        f"本次是否执行真实来源采集：{collection_context.get('collected', '未知')}\n"
        f"已接入来源数量：{collection_context.get('connected_source_count', '未知')}\n"
        "来源状态概览：\n"
        f"{collection_context.get('source_overview', '无')}\n\n"
        "解析质量概览：\n"
        f"{collection_context.get('quality_overview', '无')}\n\n"
        f"是否生成解析质量诊断：{collection_context.get('quality_generated', '未知')}\n"
        f"来源可达性概览：{collection_context.get('health_status', '未知')}\n"
        f"页面变化状态概览：{collection_context.get('page_change_status', '未知')}\n"
        f"本次采集条目数量：{collection_context.get('item_count', '未知')}\n"
        f"新增条目数量：{collection_context.get('new_items', '未知')}\n"
        f"内容变化条目数量：{collection_context.get('changed_items', '未知')}\n"
        f"未变化条目数量：{collection_context.get('unchanged_items', '未知')}\n"
        "\n官方条目抽取情况：\n"
        f"- 条目级记录：{collection_context.get('item_level_items', '0')}\n"
        f"- 页面级 fallback：{collection_context.get('page_level_items', '0')}\n"
        f"- baseline 条目：{collection_context.get('baseline_items', '0')}\n"
        f"{collection_context.get('item_extraction_overview', '暂无官方条目抽取结果。')}\n"
        f"{baseline_note}"
        "官方详情解析情况：\n"
        f"{collection_context.get('detail_extraction_overview', '暂无官方详情解析结果。')}\n"
        "详情失败类型：\n"
        f"{collection_context.get('detail_failure_overview', '本轮没有详情解析失败。')}\n"
        f"{historical_reuse_note}"
        "条目生命周期情况：\n"
        f"- 新增：{collection_context.get('lifecycle_new_items', '0')}（本轮首次发现，不自动等于官方本周首次发布）\n"
        f"- 内容变化：{collection_context.get('lifecycle_changed_items', '0')}\n"
        f"- 解析质量提升：{collection_context.get('lifecycle_extraction_improved', '0')}（不代表官方事实变化）\n"
        f"- 暂时消失：{collection_context.get('lifecycle_temporarily_missing', '0')}（本轮索引未发现，未判定删除）\n"
        f"- 长期未见：{collection_context.get('lifecycle_long_absent', '0')}（不代表官方删除或下线）\n"
        f"- 详情抓取失败：{collection_context.get('lifecycle_fetch_failed', '0')}（保留最近一次成功数据）\n"
        f"- 抓取恢复：{collection_context.get('lifecycle_recovered', '0')}（采集链路恢复，不代表官方服务恢复）\n"
        f"- 重新出现：{collection_context.get('lifecycle_reappeared', '0')}（不代表重新发布）\n"
        f"- 需要关注：{collection_context.get('lifecycle_attention_items', '0')}\n\n"
        "运行健康状态（报告生成时点快照）：\n"
        f"- Health phase：{collection_context.get('health_phase', 'provisional')}\n"
        f"- Is final：{collection_context.get('health_is_final', 'false')}\n"
        f"- 整体：{collection_context.get('overall_health', 'unknown')}\n"
        f"- 来源采集：{collection_context.get('health_source_collection', 'unknown')}\n"
        f"- 详情解析：{collection_context.get('health_detail_extraction', 'unknown')}\n"
        f"- 生命周期：{collection_context.get('health_lifecycle', 'unknown')}\n"
        f"- LLM：{collection_context.get('health_llm', 'unknown')}\n"
        f"- 输出检查：{collection_context.get('health_output_validation', 'unknown')}\n"
        f"- 项目审计：{collection_context.get('health_project_audit', 'unknown')}\n"
        "- 当前邮件投递状态：发送完成后由最终运行健康报告记录。\n"
        "- Gitee 同步状态：同步完成后由最终运行健康报告记录。\n"
        "- pending_at_render_time 不是失败。\n"
        f"- {collection_context.get('health_timing_note', '运行结束后的最终状态以 GitHub Actions Summary 和 data/run_health.json 为准。')}\n\n"
        "本轮告警：\n"
        f"- Info：{collection_context.get('alert_info', '0')}\n"
        f"- Warning：{collection_context.get('alert_warning', '0')}\n"
        f"- High：{collection_context.get('alert_high', '0')}\n"
        f"- Critical：{collection_context.get('alert_critical', '0')}\n"
        f"- Open conditions：{collection_context.get('alert_open_conditions', '0')}\n"
        f"- Resolved：{collection_context.get('resolved_alerts', '0')}\n"
        f"{collection_context.get('alert_empty_note', '')}\n"
        "告警等级仅表示自动化运行中的人工复查优先级，不表示 Starlink 或 SpaceX 事件的影响等级。\n\n"
        "页面级监测解释：\n"
        f"{collection_context.get('llm_monitoring_overview', '暂无页面级监测解释。')}\n\n"
        "附件：\n"
        f"{attachment_lines}\n\n"
        "说明：\n"
        "- 总结版适合快速阅读和组会分享；\n"
        "- 明细版适合来源复查、结构化数据核验和知识库维护；\n"
        "- 历史周报可通过 weekly/index.md 查看。\n\n"
        "页面变化状态只反映 hash 变化检测结果；解析质量只表示当前规则解析完整度，不代表事实判断。\n\n"
        "以下为本次生成的总结版 Markdown 正文：\n\n"
        f"{markdown_text}\n"
    )
    message.set_content(body)
    for attachment in attachments:
        attachment_text = attachment.read_text(encoding="utf-8")
        message.add_attachment(
            attachment_text.encode("utf-8"),
            maintype="text",
            subtype="markdown",
            filename=attachment.name,
        )
    return message


def send_weekly_email(
    markdown_path: str | Path,
    week_id: str,
    collection_context: dict[str, str] | None = None,
    attachment_paths: list[str | Path] | None = None,
) -> bool:
    """Send the weekly Markdown as email body and attachment."""
    path = Path(markdown_path)
    attachments = [Path(item) for item in (attachment_paths or [path])]
    config, missing = _get_config()

    if missing:
        print("邮件配置缺失，已取消发送。请先运行 python scripts/validate_env.py 检查配置。")
        print("缺失配置项：")
        for name in missing:
            print(f"- {name}")
        return False

    if not path.exists():
        print(f"邮件发送失败：附件路径不存在：{path}")
        return False
    for attachment in attachments:
        if not attachment.exists():
            print(f"邮件发送失败：附件路径不存在：{attachment}")
            return False

    recipients = _split_recipients(config["MAIL_TO"])
    if not recipients:
        print("邮件发送失败：MAIL_TO 未配置有效收件人。")
        return False

    try:
        port = int(config["SMTP_PORT"])
    except ValueError:
        print("邮件发送失败：SMTP_PORT 必须是数字。请先运行 python scripts/validate_env.py 检查配置。")
        return False

    message = build_message(path, week_id, config, collection_context=collection_context, attachment_paths=attachments)

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(config["SMTP_HOST"], port, context=context, timeout=30) as server:
            server.login(config["SMTP_USER"], config["SMTP_PASSWORD"])
            server.send_message(message)
        print(f"邮件发送成功：{', '.join(recipients)}")
        return True
    except smtplib.SMTPAuthenticationError:
        print("邮件发送失败：SMTP 认证失败。")
        print("请检查 SMTP 授权码是否正确、邮箱 SMTP 服务是否开启、SMTP_USER 是否为正确发件账号。")
        return False
    except (socket.gaierror, TimeoutError, ConnectionRefusedError, smtplib.SMTPConnectError):
        print("邮件发送失败：无法连接 SMTP 服务器。")
        print("请检查网络连接、SMTP_HOST、SMTP_PORT，以及当前网络是否允许访问 SMTP 服务。")
        return False
    except smtplib.SMTPRecipientsRefused:
        print("邮件发送失败：收件人地址被 SMTP 服务器拒绝，请检查 MAIL_TO。")
        return False
    except smtplib.SMTPSenderRefused:
        print("邮件发送失败：发件人地址被 SMTP 服务器拒绝，请检查 MAIL_FROM 和 SMTP_USER。")
        return False
    except smtplib.SMTPException as exc:
        print(f"邮件发送失败：SMTP 服务返回错误：{exc.__class__.__name__}")
        print("请检查 SMTP 配置和邮箱服务状态。敏感信息未输出。")
        return False
    except OSError:
        print("邮件发送失败：网络或系统连接异常。")
        print("请检查网络、SMTP_HOST、SMTP_PORT 和本机代理/防火墙设置。")
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="发送 Starlink 情报周报自动化测试邮件。")
    parser.add_argument("markdown_file", help="要发送的 Markdown 文件路径。")
    parser.add_argument("--week-id", help="周报编号，例如 2026-W25；默认使用文件名。")
    parser.add_argument("--attachment", action="append", default=[], help="可重复提供 Markdown 附件路径。")
    args = parser.parse_args()

    markdown_path = Path(args.markdown_file)
    week_id = args.week_id or markdown_path.stem
    attachment_paths = [Path(value) for value in args.attachment] or [markdown_path]
    details_path = next((path for path in attachment_paths if path.name.endswith("-details.md")), None)
    context = build_context_from_outputs(markdown_path, week_id, details_path)
    return 0 if send_weekly_email(markdown_path, week_id, collection_context=context, attachment_paths=attachment_paths) else 1


if __name__ == "__main__":
    sys.exit(main())
