from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
from datetime import datetime
from pathlib import Path

from collect_sources import (
    EXTRACTION_QUALITY_FILE,
    ITEMS_FILE,
    SOURCE_STATUS_FILE,
    collect_all_sources,
    load_extraction_quality,
    load_items,
    load_source_status,
)
from send_email import send_weekly_email


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WEEKLY_DIR = PROJECT_ROOT / "weekly"
DOCS_DIR = PROJECT_ROOT / "docs"
KNOWLEDGE_BASE = DOCS_DIR / "starlink_knowledge_base.md"
WEEKLY_ARCHIVE_INDEX = WEEKLY_DIR / "index.md"
WEEKLY_MANIFEST_FILE = PROJECT_ROOT / "data" / "weekly_manifest.json"
RUN_HISTORY_FILE = PROJECT_ROOT / "data" / "run_history.jsonl"
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
        "collect_sources": "是" if collect_enabled else "否",
        "quality_generated": "否",
        "output_mode": output_mode,
        "source_names": "无",
        "source_item_count": "0",
        "new_items": "0",
        "changed_items": "0",
        "unchanged_items": "0",
        "health_status": "unknown",
        "page_change_status": "unknown",
        "http_status": "unknown",
        "last_checked_at": "未知",
        "source_status_path": str(SOURCE_STATUS_FILE),
        "items_path": str(ITEMS_FILE),
        "quality_path": str(EXTRACTION_QUALITY_FILE),
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
    }


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
        "| 来源 | 主导解析层级 | 主导质量 | 平均置信度 | 候选链接数 |",
        "|---|---|---|---:|---:|",
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
                    escape_table_cell(quality.get("candidate_links_total") or status.get("candidate_links_total") or 0),
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
        "| 来源 | 主导解析层级 | 主导质量 | 平均置信度 | 页面级 | 链接级 | 条目级 | 候选链接数 | 解析器版本 |",
        "|---|---|---|---:|---:|---:|---:|---:|---|",
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
                    escape_table_cell(quality.get("candidate_links_total") or status.get("candidate_links_total") or 0),
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
    changed_items = [item for item in source_items if item.get("change_status") in {"new", "changed"}]
    if not changed_items:
        return "本周未检测到新增或内容变化条目。"

    rows = [
        "| 标题 | 来源 | 条目状态 | 解析层级 | 链接 |",
        "|---|---|---|---|---|",
    ]
    for item in changed_items:
        rows.append(
            "| "
            + " | ".join(
                [
                    escape_table_cell(item.get("title", "")),
                    escape_table_cell(item.get("source_name", "")),
                    escape_table_cell(item.get("change_status", "")),
                    escape_table_cell(item.get("extracted_level", "unknown")),
                    format_link(item.get("url")),
                ]
            )
            + " |"
        )
    return "\n".join(rows)


def render_page_change_notes(source_statuses: dict[str, dict[str, object]]) -> str:
    if not source_statuses:
        return "本次没有页面级变化检测记录。"
    rows = [
        f"- {status.get('source_name', source_id)}：页面变化状态为 {status.get('change_status', 'unknown')}。"
        for source_id, status in source_statuses.items()
    ]
    rows.append("以上仅为页面 hash 或采集状态检测结果，不做事实推断。")
    return "\n".join(rows)


def render_recent_run_summary(meta: dict[str, str]) -> str:
    return "\n".join(
        [
            f"- 运行时间：{meta.get('run_time', '未知')}",
            f"- ISO 周编号：{meta.get('iso_week', '未知')}",
            f"- 输出模式：{meta.get('output_mode', '未知')}",
            f"- 是否发送邮件：{meta.get('send_email', '未知')}",
            f"- 是否执行真实来源采集：{meta.get('collect_sources', '未知')}",
            f"- 是否生成解析质量诊断：{meta.get('quality_generated', '未知')}",
            f"- 已接入来源数量：{meta.get('connected_source_count', '未知')}",
            f"- 新增条目数：{meta.get('new_items', '未知')}",
            f"- 内容变化条目数：{meta.get('changed_items', '未知')}",
            f"- 未变化条目数：{meta.get('unchanged_items', '未知')}",
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
                    f"  - 是否发送邮件：{record.get('send_email', '未知')}",
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


def build_weekly_summary_markdown(
    meta: dict[str, str],
    source_items: list[dict[str, object]],
    source_statuses: dict[str, dict[str, object]],
    quality_sources: dict[str, dict[str, object]],
) -> str:
    week_id = meta["iso_week"]
    return f"""# Starlink 情报周报总结版：{week_id}

## 1. 本周概览

本周自动化流程已运行。当前系统接入两个官方来源：
- Starlink Official Updates
- SpaceX Official Launches

当前阶段为阶段 2E：周报双文档输出结构优化。

## 2. 本周核心结论

- 本周接入来源数量：{meta["connected_source_count"]}
- 可达来源数量：{meta["reachable_source_count"]}
- 页面发生变化的来源数量：{meta["page_changed_source_count"]}
- 新增条目数量：{meta["new_items"]}
- 内容变化条目数量：{meta["changed_items"]}
- 未变化条目数量：{meta["unchanged_items"]}
- 当前解析质量总体判断：{meta["overall_quality"]}

说明：本节仅基于规则化网页采集、hash 变化检测和解析质量诊断，不包含大模型事实推理。

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
- 后续可在解析质量增强后再引入大模型摘要。

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
) -> str:
    error_note = ""
    if collection_errors:
        error_note = "\n\n采集提示：本次采集存在错误，脚本已优雅处理，未输出任何密钥。"
    week_id = meta["iso_week"]
    return f"""# Starlink 情报周报明细版：{week_id}

## 1. 文档说明

本明细版用于来源复查、结构化数据核验和知识库维护。内容来自规则化网页采集、hash 变化检测和解析质量诊断，不包含大模型事实推理。{error_note}

## 2. 数据文件

| 文件 | 说明 |
|---|---|
| `data/items.jsonl` | 结构化采集条目 |
| `data/source_status.json` | 来源状态与变化检测 |
| `data/extraction_quality.json` | 解析质量诊断 |

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

## 8. 局限性

- 当前仅接入两个官方来源；
- 当前仅进行规则化静态 HTML 解析；
- 动态渲染页面可能只能形成页面级记录；
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
) -> str:
    # Legacy mode keeps the old single-file shape but rewrites bounded content instead of appending forever.
    return build_weekly_details_markdown(
        meta=meta,
        source_items=source_items,
        collection_errors=collection_errors,
        source_statuses=source_statuses,
        quality_sources=quality_sources,
        history_records=history_records,
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
) -> None:
    history_records = load_existing_history([paths["details"], paths["index"]])
    history_records.append(meta)
    history_records = history_records[-max_records:]

    summary_content = build_weekly_summary_markdown(meta, source_items, source_statuses, quality_sources)
    details_content = build_weekly_details_markdown(
        meta,
        source_items,
        collection_errors,
        source_statuses,
        quality_sources,
        history_records,
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
        "notes": "输出质量检查由 scripts/check_outputs.py 执行；本记录不保存任何 Secrets。",
    }
    records = load_run_history()
    records.append(record)
    records = records[-max_run_history:]
    write_run_history(records)
    print(f"已追加运行历史：{RUN_HISTORY_FILE}")


def latest_items_for_report(max_source_items: int, source_statuses: dict[str, dict[str, object]] | None = None) -> list[dict[str, object]]:
    items = load_items(ITEMS_FILE)
    items = sorted(items, key=lambda item: str(item.get("last_seen_at") or item.get("fetched_at") or ""), reverse=True)
    if not source_statuses:
        return items[:max_source_items]

    selected: list[dict[str, object]] = []
    for source_id in source_statuses:
        source_items = [item for item in items if item.get("source_id") == source_id]
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
        links = quality.get("candidate_links_total") or status.get("candidate_links_total") or 0
        lines.append(f"- {source_name}：{level} / {source_quality} / 平均置信度 {confidence} / 候选链接 {links}")
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
    meta["source_overview"] = "\n".join(
        f"- {status.get('source_name', source_id)}：{status.get('health_status', 'unknown')} / "
        f"{status.get('change_status', 'unknown')} / 新增{status.get('new_items', 0)} / "
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
    heading = "## 最近一次自动化运行记录"
    new_section = f"""{heading}

- 运行时间：{meta["run_time"]}
- ISO 周编号：{meta["iso_week"]}
- 执行环境：{meta["environment"]}
- Python 版本：{meta["python_version"]}
- 输出模式：{meta["output_mode"]}
- 是否发送邮件：{meta["send_email"]}
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
    parser = argparse.ArgumentParser(description="生成 Starlink 情报周报自动化测试文档。")
    parser.add_argument("--no-email", action="store_true", help="只生成 Markdown，不发送邮件。")
    parser.add_argument("--dry-run", action="store_true", help="打印将要执行的操作，不写文件、不发邮件。")
    parser.add_argument("--no-collect", action="store_true", help="不执行真实来源采集，只生成周报。")
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
    args = parser.parse_args()

    if args.max_history_records < 1:
        print("--max-history-records 必须是大于等于 1 的整数。")
        return 2
    if args.max_source_items < 1:
        print("--max-source-items 必须是大于等于 1 的整数。")
        return 2
    if args.max_run_history < 1:
        print("--max-run-history 必须是大于等于 1 的整数。")
        return 2

    send_email_enabled = not args.no_email and not args.dry_run
    collect_enabled = not args.no_collect
    meta = get_run_metadata(send_email_enabled, collect_enabled, args.output_mode)
    paths = weekly_output_paths(meta["iso_week"])
    meta["summary_path"] = f"weekly/{paths['summary'].name}"
    meta["details_path"] = f"weekly/{paths['details'].name}"
    meta["index_path"] = f"weekly/{paths['index'].name}"

    collection_result = None
    collection_errors: list[str] = []
    source_items: list[dict[str, object]] = []
    source_statuses: dict[str, dict[str, object]] = {}
    quality_sources: dict[str, dict[str, object]] = {}

    print("开始执行 Starlink 情报周报自动化测试。")
    print(f"项目根目录：{PROJECT_ROOT}")
    print(f"当前 ISO 周编号：{meta['iso_week']}")
    print(f"输出模式：{args.output_mode}")
    print(f"是否发送邮件：{meta['send_email']}")
    print(f"是否执行真实来源采集：{meta['collect_sources']}")
    print("当前阶段：2F 周报归档、历史索引与输出质量检查。")
    print(f"自动化测试记录最多保留：{args.max_history_records} 条")
    print(f"周报真实来源记录每个来源最多展示：{args.max_source_items} 条")
    meta["max_source_items"] = str(args.max_source_items)

    if args.no_collect:
        print("已按 --no-collect 参数跳过真实来源采集。")
        source_statuses = load_statuses_for_report()
        quality_sources = load_quality_for_report()
        apply_status_to_meta(meta, source_statuses)
        apply_quality_to_meta(meta, quality_sources, source_statuses)
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
        source_items = collection_result.items or latest_items_for_report(args.max_source_items, source_statuses)

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

    if args.dry_run:
        print("[dry-run] 已完成演练，不会发送邮件。")
        return 0

    if args.no_email:
        print("已按 --no-email 参数跳过邮件发送。")
        return 0

    print("开始发送邮件。")
    collection_context = {
        "stage": "2F",
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
        "summary_file": paths["summary"].name,
        "details_file": paths["details"].name,
        "index_file": paths["index"].name,
        "weekly_archive_index": "weekly/index.md",
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
