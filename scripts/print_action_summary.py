from __future__ import annotations

import json
import os
import platform
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ITEMS_FILE = PROJECT_ROOT / "data" / "items.jsonl"
SOURCE_STATUS_FILE = PROJECT_ROOT / "data" / "source_status.json"
EXTRACTION_QUALITY_FILE = PROJECT_ROOT / "data" / "extraction_quality.json"
ITEM_EXTRACTION_STATE_FILE = PROJECT_ROOT / "data" / "item_extraction_state.json"
ITEM_EXTRACTION_REPORT_FILE = PROJECT_ROOT / "data" / "item_extraction_report.json"
DETAIL_EXTRACTION_DIAGNOSTICS_FILE = PROJECT_ROOT / "data" / "detail_extraction_diagnostics.json"
WEEKLY_MANIFEST_FILE = PROJECT_ROOT / "data" / "weekly_manifest.json"
RUN_HISTORY_FILE = PROJECT_ROOT / "data" / "run_history.jsonl"
LLM_AUDIT_FILE = PROJECT_ROOT / "data" / "llm_audit.json"
LLM_SUMMARY_FILE = PROJECT_ROOT / "data" / "llm_summaries.json"
LLM_USAGE_FILE = PROJECT_ROOT / "data" / "llm_usage.jsonl"
ITEM_LIFECYCLE_STATE_FILE = PROJECT_ROOT / "data" / "item_lifecycle_state.json"
ITEM_VERSIONS_FILE = PROJECT_ROOT / "data" / "item_versions.jsonl"
LIFECYCLE_EVENTS_FILE = PROJECT_ROOT / "data" / "lifecycle_events.jsonl"
LIFECYCLE_REPORT_FILE = PROJECT_ROOT / "data" / "lifecycle_report.json"
LIFECYCLE_REPLAY_REPORT_FILE = PROJECT_ROOT / "data" / "lifecycle_replay_report.json"
ALERT_STATE_FILE = PROJECT_ROOT / "data" / "alert_state.json"
ALERT_EVENTS_FILE = PROJECT_ROOT / "data" / "alert_events.jsonl"
ALERT_REPORT_FILE = PROJECT_ROOT / "data" / "alert_report.json"
RUN_HEALTH_FILE = PROJECT_ROOT / "data" / "run_health.json"
RUN_HEALTH_HISTORY_FILE = PROJECT_ROOT / "data" / "run_health_history.jsonl"


def _yes_no(value: bool) -> str:
    return "是" if value else "否"


def _escape_table_cell(value: object) -> str:
    return str(value if value is not None else "").replace("\n", " ").replace("\r", " ").replace("|", "\\|")


def _usage_metric(value: object) -> object:
    return "unknown" if value is None else value


def _source_statuses() -> tuple[bool, dict[str, dict[str, object]]]:
    if not SOURCE_STATUS_FILE.exists():
        return False, {}

    try:
        data = json.loads(SOURCE_STATUS_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return True, {
            "source_status_parse_error": {
                "source_name": "source_status.json",
                "health_status": "无法解析",
                "change_status": "无法解析",
                "new_items": 0,
                "changed_items": 0,
                "unchanged_items": 0,
            }
        }

    sources = data.get("sources", {})
    return True, sources if isinstance(sources, dict) else {}


def _extraction_quality() -> tuple[bool, dict[str, dict[str, object]]]:
    if not EXTRACTION_QUALITY_FILE.exists():
        return False, {}

    try:
        data = json.loads(EXTRACTION_QUALITY_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return True, {
            "extraction_quality_parse_error": {
                "source_name": "extraction_quality.json",
                "dominant_extracted_level": "无法解析",
                "dominant_source_quality": "无法解析",
                "average_confidence": 0,
                "candidate_links_total": 0,
                "parser_version": "unknown",
            }
        }

    sources = data.get("sources", {})
    return True, sources if isinstance(sources, dict) else {}


def _llm_audit() -> dict[str, object]:
    if not LLM_AUDIT_FILE.exists():
        return {
            "llm_enabled": "unknown",
            "llm_provider": "unknown",
            "llm_status": "unknown",
            "model": "unknown",
            "base_url_label": "unknown",
            "summary_generated": "unknown",
        }
    try:
        data = json.loads(LLM_AUDIT_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {
            "llm_enabled": "unknown",
            "llm_provider": "unknown",
            "llm_status": "invalid_json",
            "model": "unknown",
            "base_url_label": "unknown",
            "summary_generated": "unknown",
        }
    return data if isinstance(data, dict) else {}


def _item_extraction_report() -> dict[str, dict[str, object]]:
    if not ITEM_EXTRACTION_REPORT_FILE.exists():
        return {}
    try:
        data = json.loads(ITEM_EXTRACTION_REPORT_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    sources = data.get("sources", {}) if isinstance(data, dict) else {}
    return sources if isinstance(sources, dict) else {}


def _lifecycle_report() -> dict[str, object]:
    if not LIFECYCLE_REPORT_FILE.exists():
        return {}
    try:
        data = json.loads(LIFECYCLE_REPORT_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _json_file(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _jsonl_file(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    rows: list[dict[str, object]] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            value = json.loads(line)
            if isinstance(value, dict):
                rows.append(value)
    except json.JSONDecodeError:
        return []
    return rows


def _week_id() -> str:
    now = datetime.now().astimezone()
    iso = now.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def main() -> int:
    status_exists, statuses = _source_statuses()
    quality_exists, quality_sources = _extraction_quality()
    gitee_configured = bool(os.getenv("GITEE_REMOTE", "").strip())
    gitee_sync_status = os.getenv("GITEE_SYNC_STATUS", "unknown").strip() or "unknown"
    output_check_status = os.getenv("OUTPUT_CHECK_STATUS", "unknown").strip() or "unknown"
    project_audit_status = os.getenv("PROJECT_AUDIT_STATUS", "unknown").strip() or "unknown"
    llm_audit = _llm_audit()
    item_reports = _item_extraction_report()
    lifecycle_report = _lifecycle_report()
    lifecycle_sources = lifecycle_report.get("sources", {}) if isinstance(lifecycle_report, dict) else {}
    lifecycle_sources = lifecycle_sources if isinstance(lifecycle_sources, dict) else {}
    lifecycle_totals = lifecycle_report.get("totals", {}) if isinstance(lifecycle_report, dict) else {}
    lifecycle_totals = lifecycle_totals if isinstance(lifecycle_totals, dict) else {}
    lifecycle_rows = []
    for source_id, source in lifecycle_sources.items():
        source = source if isinstance(source, dict) else {}
        lifecycle_rows.append(
            "| "
            + " | ".join(
                [
                    _escape_table_cell(source.get("source_name") or source_id),
                    _escape_table_cell(source.get("active", 0)),
                    _escape_table_cell(source.get("new", 0)),
                    _escape_table_cell(source.get("changed", 0)),
                    _escape_table_cell(source.get("extraction_improved", 0)),
                    _escape_table_cell(source.get("temporarily_missing", 0)),
                    _escape_table_cell(source.get("long_absent", 0)),
                    _escape_table_cell(source.get("fetch_failed", 0)),
                    _escape_table_cell(source.get("recovered", 0)),
                    _escape_table_cell(source.get("reappeared", 0)),
                    _escape_table_cell(source.get("attention", 0)),
                ]
            )
            + " |"
        )
    if not lifecycle_rows:
        lifecycle_rows.append("| unknown | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |")
    run_health = _json_file(RUN_HEALTH_FILE)
    alert_report = _json_file(ALERT_REPORT_FILE)
    alert_totals = alert_report.get("totals", {}) if isinstance(alert_report.get("totals"), dict) else {}
    components = run_health.get("components", {}) if isinstance(run_health.get("components"), dict) else {}
    health_rows = []
    for component_name in (
        "source_collection", "candidate_discovery", "detail_extraction", "lifecycle", "llm",
        "output_validation", "project_audit", "email", "gitee_sync",
    ):
        component = components.get(component_name, {}) if isinstance(components.get(component_name), dict) else {}
        health_rows.append(
            f"| {_escape_table_cell(component_name)} | {_escape_table_cell(component.get('status', 'unknown'))} | "
            f"{_escape_table_cell(component.get('result', ''))} |"
        )
    health_history = _jsonl_file(RUN_HEALTH_HISTORY_FILE)
    recent_health = ", ".join(str(row.get("overall_health", "unknown")) for row in health_history[-4:]) or "unknown"
    replay_report = _json_file(LIFECYCLE_REPLAY_REPORT_FILE)
    usage = llm_audit.get("usage", {}) if isinstance(llm_audit.get("usage"), dict) else {}
    week_id = _week_id()

    lines = [
        "## Starlink Weekly Automation",
        "",
        "- 阶段：4D",
        f"- 工作流名称：{os.getenv('GITHUB_WORKFLOW', 'unknown')}",
        f"- 分支：{os.getenv('GITHUB_REF_NAME', 'unknown')}",
        f"- 触发方式：{os.getenv('GITHUB_EVENT_NAME', 'unknown')}",
        f"- Python 版本：{platform.python_version()}",
        f"- 本次运行是否成功：{os.getenv('ACTION_RUN_STATUS', 'unknown')}",
        "- 更新文件路径：docs/starlink_knowledge_base.md、weekly/",
        "- 是否执行真实来源采集：是",
        "- 数据文件路径：data/items.jsonl",
        "- source_status.json 路径：data/source_status.json",
        "- extraction_quality.json 路径：data/extraction_quality.json",
        "- item_extraction_state.json 路径：data/item_extraction_state.json",
        "- item_extraction_report.json 路径：data/item_extraction_report.json",
        "- detail_extraction_diagnostics.json 路径：data/detail_extraction_diagnostics.json",
        "- llm_audit.json 路径：data/llm_audit.json",
        "- item_lifecycle_state.json 路径：data/item_lifecycle_state.json",
        "- item_versions.jsonl 路径：data/item_versions.jsonl",
        "- lifecycle_events.jsonl 路径：data/lifecycle_events.jsonl",
        "- lifecycle_report.json 路径：data/lifecycle_report.json",
        "- lifecycle_replay_report.json 路径：data/lifecycle_replay_report.json",
        "- alert_state.json 路径：data/alert_state.json",
        "- alert_events.jsonl 路径：data/alert_events.jsonl",
        "- alert_report.json 路径：data/alert_report.json",
        "- run_health.json 路径：data/run_health.json",
        "- run_health_history.jsonl 路径：data/run_health_history.jsonl",
        "- sources.yml 路径：sources.yml",
        f"- items.jsonl 是否存在：{_yes_no(ITEMS_FILE.exists())}",
        f"- source_status.json 是否存在：{_yes_no(status_exists)}",
        f"- extraction_quality.json 是否存在：{_yes_no(quality_exists)}",
        f"- item_extraction_state.json 是否存在：{_yes_no(ITEM_EXTRACTION_STATE_FILE.exists())}",
        f"- item_extraction_report.json 是否存在：{_yes_no(ITEM_EXTRACTION_REPORT_FILE.exists())}",
        f"- detail_extraction_diagnostics.json 是否存在：{_yes_no(DETAIL_EXTRACTION_DIAGNOSTICS_FILE.exists())}",
        f"- weekly_manifest.json 是否存在：{_yes_no(WEEKLY_MANIFEST_FILE.exists())}",
        f"- run_history.jsonl 是否存在：{_yes_no(RUN_HISTORY_FILE.exists())}",
        f"- llm_audit.json 是否存在：{_yes_no(LLM_AUDIT_FILE.exists())}",
        f"- llm_usage.jsonl 是否存在：{_yes_no(LLM_USAGE_FILE.exists())}",
        f"- item_lifecycle_state.json 是否存在：{_yes_no(ITEM_LIFECYCLE_STATE_FILE.exists())}",
        f"- item_versions.jsonl 是否存在：{_yes_no(ITEM_VERSIONS_FILE.exists())}",
        f"- lifecycle_events.jsonl 是否存在：{_yes_no(LIFECYCLE_EVENTS_FILE.exists())}",
        f"- lifecycle_report.json 是否存在：{_yes_no(LIFECYCLE_REPORT_FILE.exists())}",
        f"- lifecycle replay：{_escape_table_cell(replay_report.get('passed', 'unknown'))}/{_escape_table_cell(replay_report.get('scenario_count', 'unknown'))} passed",
        f"- Gitee 同步是否配置：{_yes_no(gitee_configured)}",
        f"- Gitee 同步状态：{gitee_sync_status}",
        "",
        "### 条目生命周期",
        "",
        "| 来源 | Active | New | Changed | Improved | Temporarily Missing | Long Absent | Fetch Failed | Recovered | Reappeared | Attention |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        *lifecycle_rows,
        "",
        f"- Semantic versions：{_escape_table_cell(lifecycle_totals.get('new_semantic_versions', 0))}",
        f"- Extraction revisions：{_escape_table_cell(lifecycle_totals.get('new_extraction_revisions', 0))}",
        f"- Lifecycle events：{_escape_table_cell(lifecycle_totals.get('lifecycle_events', 0))}",
        "",
        "### 运行健康",
        "",
        f"- 整体健康状态：{_escape_table_cell(run_health.get('overall_health', 'unknown'))}",
        "",
        "| 组件 | 状态 | 说明 |",
        "|---|---|---|",
        *health_rows,
        "",
        "### 运维告警",
        "",
        f"- 整体告警状态：{_escape_table_cell(alert_report.get('overall_alert_status', 'unknown'))}",
        f"- Open conditions：{_escape_table_cell(alert_totals.get('open_conditions', 'unknown'))}",
        f"- Resolved：{_escape_table_cell(alert_totals.get('resolved', 'unknown'))}",
        "- 告警等级仅表示自动化系统中的人工复查优先级，不表示官方事件的重要程度。",
        "",
        "| 等级 | 新增 | 更新 | 升级 | 解决 | 当前 Open |",
        "|---|---:|---:|---:|---:|---:|",
        f"| Info | {_escape_table_cell(alert_totals.get('info', 0))} | {_escape_table_cell(alert_totals.get('updated', 0))} | 0 | {_escape_table_cell(alert_totals.get('resolved', 0))} | {_escape_table_cell(alert_totals.get('open_info', 0))} |",
        f"| Warning | {_escape_table_cell(alert_totals.get('warning', 0))} | {_escape_table_cell(alert_totals.get('updated', 0))} | {_escape_table_cell(alert_totals.get('escalated', 0))} | {_escape_table_cell(alert_totals.get('resolved', 0))} | {_escape_table_cell(alert_totals.get('open_warning', 0))} |",
        f"| High | {_escape_table_cell(alert_totals.get('high', 0))} | 0 | {_escape_table_cell(alert_totals.get('escalated', 0))} | {_escape_table_cell(alert_totals.get('resolved', 0))} | {_escape_table_cell(alert_totals.get('open_high', 0))} |",
        f"| Critical | {_escape_table_cell(alert_totals.get('critical', 0))} | 0 | {_escape_table_cell(alert_totals.get('escalated', 0))} | {_escape_table_cell(alert_totals.get('resolved', 0))} | {_escape_table_cell(alert_totals.get('open_critical', 0))} |",
        "",
        "### 长期运行趋势",
        "",
        f"- 历史记录数量：{len(health_history)}",
        f"- 最近 4 次 healthy/degraded/unhealthy：{recent_health}",
        f"- 来源连续失败：{sum(1 for item in (alert_report.get('open_alerts', []) or []) if isinstance(item, dict) and item.get('alert_type') == 'source_unreachable')}",
        f"- 详情成功率趋势：{', '.join(str(row.get('detail_success_rate', 'unknown')) for row in health_history[-4:]) or 'unknown'}",
        f"- LLM 连续 validation failure：{sum(1 for item in (alert_report.get('open_alerts', []) or []) if isinstance(item, dict) and item.get('alert_type') == 'llm_validation_failed')}",
        "",
        "### 官方条目抽取",
        "",
        "| 来源 | 解析器 | 静态候选 | 渲染候选 | 候选总数 | 静态详情成功 | 渲染详情成功 | 最终成功 | 失败 | 成功率 | Baseline | 新增 | 变化 | 未变化 | 层级 | 质量 |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|",
        "",
        "### 详情失败类型",
        "",
        "| 来源 | 错误类型 | 数量 |",
        "|---|---|---:|",
        "",
        "### 本周输出文档",
        "",
        "| 类型 | 路径 |",
        "|---|---|",
        f"| 总结版 | weekly/{week_id}-summary.md |",
        f"| 明细版 | weekly/{week_id}-details.md |",
        f"| 兼容索引 | weekly/{week_id}.md |",
        "",
        "### 周报归档",
        "",
        "| 类型 | 路径 |",
        "|---|---|",
        "| 周报总索引 | weekly/index.md |",
        "| 周报 manifest | data/weekly_manifest.json |",
        "| 运行历史 | data/run_history.jsonl |",
        "",
        "### 输出质量检查",
        "",
        f"- 检查状态：{output_check_status}",
        "- 检查脚本：scripts/check_outputs.py",
        "",
        "### 稳定性与配置审计",
        "",
        f"- 审计状态：{project_audit_status}",
        "- 审计脚本：scripts/audit_project.py",
        "- 部署检查清单：docs/deployment_checklist.md",
        "- 运维指南：docs/operations_guide.md",
        "- 发布说明：RELEASE_NOTES.md",
        "",
        "### 大模型摘要状态",
        "",
        "| 字段 | 状态 |",
        "|---|---|",
        f"| LLM 是否启用 | {_escape_table_cell(llm_audit.get('llm_enabled', 'unknown'))} |",
        f"| LLM Provider | {_escape_table_cell(llm_audit.get('llm_provider', 'unknown'))} |",
        f"| 模型 | {_escape_table_cell(llm_audit.get('model', 'unknown'))} |",
        f"| Base URL 类型 | {_escape_table_cell(llm_audit.get('base_url_label', 'unknown'))} |",
        f"| LLM 状态 | {_escape_table_cell(llm_audit.get('llm_status', 'unknown'))} |",
        f"| 摘要是否生成 | {_escape_table_cell(llm_audit.get('summary_generated', 'unknown'))} |",
        f"| 原始候选记录 | {_escape_table_cell(llm_audit.get('raw_candidate_records', llm_audit.get('input_records_before_dedup', 'unknown')))} |",
        f"| URL 去重后记录 | {_escape_table_cell(llm_audit.get('records_after_url_dedup', llm_audit.get('input_records_after_dedup', 'unknown')))} |",
        f"| 最终核心输入记录 | {_escape_table_cell(llm_audit.get('final_core_input_records', llm_audit.get('input_records', 'unknown')))} |",
        f"| 最终核心唯一 URL | {_escape_table_cell(llm_audit.get('final_core_unique_urls', 'unknown'))} |",
        f"| 复用历史记录 | {_escape_table_cell(llm_audit.get('reused_historical_records', 'unknown'))} |",
        f"| 删除重复记录 | {_escape_table_cell(llm_audit.get('duplicate_records_removed', 'unknown'))} |",
        f"| 唯一来源 URL | {_escape_table_cell(llm_audit.get('unique_source_urls', 'unknown'))} |",
        f"| 移除非法 record ID | {_escape_table_cell(llm_audit.get('invalid_record_ids_removed', 'unknown'))} |",
        f"| 移除非法 URL | {_escape_table_cell(llm_audit.get('invalid_urls_removed', 'unknown'))} |",
        f"| 补齐缺失 record ID | {_escape_table_cell(llm_audit.get('missing_record_ids_repaired', 'unknown'))} |",
        f"| 补齐缺失 URL | {_escape_table_cell(llm_audit.get('missing_urls_repaired', 'unknown'))} |",
        f"| 删除无来源要点 | {_escape_table_cell(llm_audit.get('key_points_removed_without_sources', 'unknown'))} |",
        f"| 引用对齐状态 | {_escape_table_cell(llm_audit.get('reference_alignment_status', 'unknown'))} |",
        f"| Prompt tokens | {_escape_table_cell(_usage_metric(usage.get('prompt_tokens')))} |",
        f"| Completion tokens | {_escape_table_cell(_usage_metric(usage.get('completion_tokens')))} |",
        f"| Total tokens | {_escape_table_cell(_usage_metric(usage.get('total_tokens')))} |",
        f"| API 调用耗时 | {_escape_table_cell(_usage_metric(usage.get('latency_ms')))} ms |",
        "| 审计文件 | data/llm_audit.json |",
        "| 摘要文件 | data/llm_summaries.json |",
        "| 用量记录 | data/llm_usage.jsonl |",
        f"| 摘要文件是否存在 | {_yes_no(LLM_SUMMARY_FILE.exists())} |",
        "",
        "### 来源状态",
        "",
        "| 来源 | 可达性 | 页面变化状态 | 新增 | 变化 | 未变化 |",
        "|---|---|---|---:|---:|---:|",
    ]
    if item_reports:
        item_rows = []
        for source_id, report in item_reports.items():
            item_rows.append(
                "| "
                + " | ".join(
                    [
                        _escape_table_cell(report.get("source_name") or source_id),
                        _escape_table_cell(report.get("parser_version", "unknown")),
                        _escape_table_cell(report.get("static_candidate_count", 0)),
                        _escape_table_cell(report.get("rendered_candidate_count", 0)),
                        _escape_table_cell(report.get("candidate_count_total", report.get("candidate_count", 0))),
                        _escape_table_cell(report.get("static_detail_success", 0)),
                        _escape_table_cell(report.get("rendered_detail_success", 0)),
                        _escape_table_cell(report.get("final_detail_success", report.get("detail_fetch_success", 0))),
                        _escape_table_cell(report.get("final_detail_failed", report.get("detail_fetch_failed", 0))),
                        _escape_table_cell("unknown" if report.get("final_success_rate") is None else f"{float(report.get('final_success_rate')):.0%}"),
                        _escape_table_cell(report.get("baseline_items", 0)),
                        _escape_table_cell(report.get("new_items", 0)),
                        _escape_table_cell(report.get("changed_items", 0)),
                        _escape_table_cell(report.get("unchanged_items", 0)),
                        _escape_table_cell(report.get("dominant_extracted_level", "unknown")),
                        _escape_table_cell(report.get("dominant_source_quality", "unknown")),
                    ]
                )
                + " |"
            )
        insertion = lines.index("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|") + 1
        lines[insertion:insertion] = item_rows
    else:
        insertion = lines.index("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|") + 1
        lines[insertion:insertion] = ["| unknown | unknown | 0 | 0 | 0 | 0 | 0 | 0 | 0 | unknown | 0 | 0 | 0 | 0 | unknown | unknown |"]
    failure_rows: list[str] = []
    for source_id, report in item_reports.items():
        failure_types = report.get("failure_types", {}) if isinstance(report, dict) else {}
        if not isinstance(failure_types, dict):
            continue
        for error_type, count in sorted(failure_types.items()):
            failure_rows.append(
                f"| {_escape_table_cell(report.get('source_name') or source_id)} | "
                f"{_escape_table_cell(error_type)} | {_escape_table_cell(count)} |"
            )
    failure_insertion = lines.index("|---|---|---:|") + 1
    lines[failure_insertion:failure_insertion] = failure_rows or ["| unknown | none | 0 |"]
    if statuses:
        for source_id, status in statuses.items():
            lines.append(
                "| "
                + " | ".join(
                    [
                        _escape_table_cell(status.get("source_name") or source_id),
                        _escape_table_cell(status.get("health_status", "unknown")),
                        _escape_table_cell(status.get("change_status", "unknown")),
                        _escape_table_cell(status.get("new_items", 0)),
                        _escape_table_cell(status.get("changed_items", 0)),
                        _escape_table_cell(status.get("unchanged_items", 0)),
                    ]
                )
                + " |"
            )
    else:
        lines.append("| unknown | unknown | unknown | 0 | 0 | 0 |")

    lines.extend(
        [
            "",
            "### 解析质量",
            "",
            "| 来源 | 主导解析层级 | 主导解析质量 | 平均置信度 | 静态候选 | 渲染候选 | 候选总数 | 解析器版本 |",
            "|---|---|---|---:|---:|---:|---:|---|",
        ]
    )
    ordered_ids = list(statuses.keys()) or list(quality_sources.keys())
    if ordered_ids:
        for source_id in ordered_ids:
            status = statuses.get(source_id, {})
            quality = quality_sources.get(source_id, {})
            lines.append(
                "| "
                + " | ".join(
                    [
                        _escape_table_cell(quality.get("source_name") or status.get("source_name") or source_id),
                        _escape_table_cell(quality.get("dominant_extracted_level") or status.get("dominant_extracted_level") or "unknown"),
                        _escape_table_cell(quality.get("dominant_source_quality") or status.get("dominant_source_quality") or "unknown"),
                        _escape_table_cell(quality.get("average_confidence") or status.get("average_confidence") or 0),
                        _escape_table_cell(quality.get("static_candidate_count") or status.get("static_candidate_count") or 0),
                        _escape_table_cell(quality.get("rendered_candidate_count") or status.get("rendered_candidate_count") or 0),
                        _escape_table_cell(quality.get("candidate_count_total") or status.get("candidate_count_total") or 0),
                        _escape_table_cell(quality.get("parser_version") or status.get("parser_version") or "unknown"),
                    ]
                )
                + " |"
            )
    else:
        lines.append("| unknown | unknown | unknown | 0 | 0 | 0 | 0 | unknown |")

    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
