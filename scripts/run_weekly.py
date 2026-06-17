from __future__ import annotations

import argparse
import platform
import sys
from datetime import datetime
from pathlib import Path

from collect_sources import ITEMS_FILE, SOURCE_STATUS_FILE, collect_all_sources, load_items, load_source_status
from send_email import send_weekly_email


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WEEKLY_DIR = PROJECT_ROOT / "weekly"
DOCS_DIR = PROJECT_ROOT / "docs"
KNOWLEDGE_BASE = DOCS_DIR / "starlink_knowledge_base.md"
HISTORY_HEADING = "## 6. 自动化测试记录"
LEGACY_HISTORY_HEADINGS = ["## 4. 自动化测试记录", "## 自动化测试记录"]
CONNECTED_SOURCES_HEADING = "## 已接入来源"
SOURCE_CHANGE_HEADING = "## 来源状态与变化检测"


def get_run_metadata(send_email_enabled: bool, collect_enabled: bool) -> dict[str, str]:
    now = datetime.now().astimezone()
    iso = now.isocalendar()
    week_id = f"{iso.year}-W{iso.week:02d}"
    return {
        "run_time": now.strftime("%Y-%m-%d %H:%M:%S %Z%z"),
        "iso_week": week_id,
        "environment": f"{platform.system()} {platform.release()}",
        "python_version": platform.python_version(),
        "send_email": "是" if send_email_enabled else "否",
        "collect_sources": "是" if collect_enabled else "否",
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
        "connected_source_count": "0",
        "source_overview": "",
    }


def escape_table_cell(value: object) -> str:
    text = "" if value is None else str(value)
    text = text.replace("\n", " ").replace("\r", " ")
    return text.replace("|", "\\|").strip()


def render_source_items_table(source_items: list[dict[str, object]]) -> str:
    if not source_items:
        return "本次未采集到有效条目。"

    rows = [
        "| 标题 | 类型 | 可信度 | 条目状态 | 采集时间 | 链接 |",
        "|---|---|---|---|---|---|",
    ]
    for item in source_items:
        title = escape_table_cell(item.get("title", ""))
        source_type = escape_table_cell(item.get("source_type", ""))
        reliability = escape_table_cell(item.get("reliability_tier", ""))
        change_status = escape_table_cell(item.get("change_status", "unknown"))
        fetched_at = escape_table_cell(item.get("last_seen_at") or item.get("fetched_at", ""))
        url = str(item.get("url") or "").strip()
        link = f"[链接]({url})" if url else ""
        rows.append(f"| {title} | {source_type} | {reliability} | {change_status} | {fetched_at} | {link} |")
    return "\n".join(rows)


def render_source_status_table(source_statuses: dict[str, dict[str, object]]) -> str:
    if not source_statuses:
        return "本次没有来源状态记录。"

    rows = [
        "| 来源 | 类别 | 类型 | 可信度 | 可达性 | 页面变化状态 | HTTP状态 | 最近检查时间 |",
        "|---|---|---|---|---|---|---|---|",
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
                ]
            )
            + " |"
        )
    return "\n".join(rows)


def render_change_detection_table(source_statuses: dict[str, dict[str, object]]) -> str:
    if not source_statuses:
        return "本次没有来源变化检测记录。"

    rows = [
        "| 来源 | 新增条目数 | 内容变化条目数 | 未变化条目数 | 页面级变化状态 |",
        "|---|---:|---:|---:|---|",
    ]
    for status in source_statuses.values():
        rows.append(
            "| "
            + " | ".join(
                [
                    escape_table_cell(status.get("source_name", "")),
                    escape_table_cell(status.get("new_items", 0)),
                    escape_table_cell(status.get("changed_items", 0)),
                    escape_table_cell(status.get("unchanged_items", 0)),
                    escape_table_cell(status.get("change_status", "")),
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


def render_grouped_source_items(
    source_items: list[dict[str, object]],
    source_statuses: dict[str, dict[str, object]],
    max_source_items: int,
) -> str:
    grouped = group_items_by_source(source_items, max_source_items)
    sections: list[str] = []
    for index, (source_id, status) in enumerate(source_statuses.items(), start=1):
        source_name = escape_table_cell(status.get("source_name") or source_id)
        sections.append(f"### 4.{index} {source_name}\n\n{render_source_items_table(grouped.get(source_id, []))}")

    for source_id, items in grouped.items():
        if source_id in source_statuses:
            continue
        source_name = escape_table_cell(items[0].get("source_name") if items else source_id)
        sections.append(f"### 4.{len(sections) + 1} {source_name}\n\n{render_source_items_table(items)}")

    return "\n\n".join(sections) if sections else "本次未采集到有效条目。"


def build_weekly_base(
    meta: dict[str, str],
    source_items: list[dict[str, object]],
    collection_errors: list[str],
    source_statuses: dict[str, dict[str, object]],
) -> str:
    week_id = meta["iso_week"]
    error_note = ""
    if collection_errors:
        error_note = "\n\n采集提示：本次采集存在错误，脚本已优雅处理，未输出任何密钥。"
    return f"""# Starlink 情报周报：{week_id}

## 1. 本周摘要

本周自动化流程已运行。当前阶段已接入两个官方来源：Starlink Official Updates 与 SpaceX Official Launches，并继续进行来源状态诊断与页面变化检测。

## 2. 来源状态诊断

{render_source_status_table(source_statuses)}

## 3. 本周变化检测

{render_change_detection_table(source_statuses)}

说明：当前阶段仅基于规则化页面抽取和 hash 变化检测，不代表事实判断。{error_note}

## 4. 真实来源采集结果

本次是否执行真实来源采集：{meta["collect_sources"]}

本次采集来源名称：{meta["source_names"]}

本次采集条目数量：{meta["source_item_count"]}

{render_grouped_source_items(source_items, source_statuses, int(meta.get("max_source_items", "10")))}

## 5. 来源说明与局限性

- 当前阶段仅接入两个官方来源：Starlink Official Updates 与 SpaceX Official Launches。
- 当前阶段仅进行规则化网页抽取，不使用大模型生成事实判断。
- 如果页面由 JavaScript 动态渲染，可能只能提取页面级记录或部分链接。
- 页面变化状态基于 hash 检测，只代表采集到的页面内容发生变化或未变化。
- 不对未提取到发布时间、发射时间、任务状态、载荷数量的信息进行编造。
- SpaceX Launches 页面用于官方发射任务信息入口，但当前阶段不使用第三方发射日程 API。
"""


def build_weekly_document(
    meta: dict[str, str],
    source_items: list[dict[str, object]],
    collection_errors: list[str],
    source_statuses: dict[str, dict[str, object]],
) -> str:
    return f"{build_weekly_base(meta, source_items, collection_errors, source_statuses)}\n{HISTORY_HEADING}\n\n{render_history_records([meta])}\n"


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
                    f"  - 是否发送邮件：{record.get('send_email', '未知')}",
                    f"  - 是否执行真实来源采集：{record.get('collect_sources', '未知')}",
                    f"  - 页面变化状态：{record.get('page_change_status', '未知')}",
                    f"  - 已接入来源数量：{record.get('connected_source_count', '未知')}",
                ]
            )
        )
    return "\n".join(rendered)


def _split_base_and_history(existing: str) -> tuple[str, str]:
    candidates = []
    for heading in [HISTORY_HEADING, *LEGACY_HISTORY_HEADINGS]:
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
        "是否发送邮件": "send_email",
        "是否执行真实来源采集": "collect_sources",
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


def merge_weekly_history(existing: str, meta: dict[str, str], max_records: int) -> str:
    base, history_text = _split_base_and_history(existing)
    records = _parse_history_records(history_text)
    records.append(meta)
    records = records[-max_records:]
    return f"{base}\n\n{HISTORY_HEADING}\n\n{render_history_records(records)}\n"


def update_knowledge_base_text(existing: str, meta: dict[str, str], source_statuses: dict[str, dict[str, object]]) -> str:
    existing = existing.replace(
        "当前阶段仅用于验证自动化链路，尚未接入真实 Starlink 信息采集、大模型总结和知识库更新功能。",
        "当前阶段已接入两个官方来源：Starlink Official Updates 与 SpaceX Official Launches。采集方式为规则化网页抽取，不包含大模型事实推理。",
    )
    existing = existing.replace(
        "当前阶段已接入第一个真实来源：Starlink 官方 Updates 页面。采集方式为规则化网页抽取，不包含大模型事实推理。",
        "当前阶段已接入两个官方来源：Starlink Official Updates 与 SpaceX Official Launches。采集方式为规则化网页抽取，不包含大模型事实推理。",
    )
    existing = ensure_connected_sources_section_text(existing)
    existing = update_source_change_section_text(existing, meta, source_statuses)
    heading = "## 最近一次自动化运行记录"
    new_section = f"""{heading}

- 运行时间：{meta["run_time"]}
- ISO 周编号：{meta["iso_week"]}
- 执行环境：{meta["environment"]}
- Python 版本：{meta["python_version"]}
- 是否发送邮件：{meta["send_email"]}
- 是否执行真实来源采集：{meta["collect_sources"]}
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


def ensure_connected_sources_section_text(existing: str) -> str:
    section = f"""{CONNECTED_SOURCES_HEADING}

| 来源 | 类型 | 可信度 | 地址 | 状态 |
|---|---|---|---|---|
| Starlink Official Updates | official | S | https://www.starlink.com/updates | 已接入 |
| SpaceX Official Launches | official | S | https://www.spacex.com/launches | 已接入 |
"""
    return replace_or_insert_section(existing, CONNECTED_SOURCES_HEADING, section, before_heading=SOURCE_CHANGE_HEADING)


def update_source_change_section_text(existing: str, _meta: dict[str, str], source_statuses: dict[str, dict[str, object]] | None = None) -> str:
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
    return replace_or_insert_section(existing, SOURCE_CHANGE_HEADING, section, before_heading="## 最近一次自动化运行记录")


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
            "当前阶段已接入两个官方来源：Starlink Official Updates 与 SpaceX Official Launches。采集方式为规则化网页抽取，不包含大模型事实推理。\n\n"
            "## 已接入来源\n\n"
            "| 来源 | 类型 | 可信度 | 地址 | 状态 |\n"
            "|---|---|---|---|---|\n"
            "| Starlink Official Updates | official | S | https://www.starlink.com/updates | 已接入 |\n"
            "| SpaceX Official Launches | official | S | https://www.spacex.com/launches | 已接入 |\n\n"
            "## 来源状态与变化检测\n\n"
            "| 来源 | 最近检查时间 | 可达性 | 页面变化状态 | 最近变化时间 | 当前状态 |\n"
            "|---|---|---|---|---|---|\n"
            "| Starlink Official Updates | 暂无 | unknown | unknown | 暂无 | 未检查 |\n"
            "| SpaceX Official Launches | 暂无 | unknown | unknown | 暂无 | 未检查 |\n\n"
            "## 最近一次自动化运行记录\n\n"
            "暂无。\n",
            encoding="utf-8",
        )


def write_weekly_file(
    weekly_path: Path,
    meta: dict[str, str],
    dry_run: bool,
    max_records: int,
    source_items: list[dict[str, object]],
    collection_errors: list[str],
    source_statuses: dict[str, dict[str, object]],
) -> None:
    if weekly_path.exists():
        print(f"检测到本周周报已存在，将更新真实来源采集结果并整理自动化测试记录：{weekly_path}")
        if dry_run:
            print(f"[dry-run] 不会实际更新周报内容；最多保留最近 {max_records} 条记录。")
            return
        existing = weekly_path.read_text(encoding="utf-8")
        _base, history_text = _split_base_and_history(existing)
        records = _parse_history_records(history_text)
        records.append(meta)
        records = records[-max_records:]
        updated = f"{build_weekly_base(meta, source_items, collection_errors, source_statuses)}\n{HISTORY_HEADING}\n\n{render_history_records(records)}\n"
        weekly_path.write_text(updated, encoding="utf-8", newline="\n")
        print(f"已更新真实来源采集结果，并限制自动化测试记录最多保留最近 {max_records} 条。")
        return

    print(f"将创建本周周报：{weekly_path}")
    if dry_run:
        print("[dry-run] 不会实际创建周报文件。")
        return

    WEEKLY_DIR.mkdir(parents=True, exist_ok=True)
    weekly_path.write_text(build_weekly_document(meta, source_items, collection_errors, source_statuses), encoding="utf-8", newline="\n")
    print("已创建本周 Markdown 周报。")


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


def apply_status_to_meta(meta: dict[str, str], source_statuses: dict[str, dict[str, object]]) -> None:
    if not source_statuses:
        return

    meta["connected_source_count"] = str(len(source_statuses))
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
        f"变化{status.get('changed_items', 0)} / 未变化{status.get('unchanged_items', 0)}"
        for source_id, status in source_statuses.items()
    )


def update_knowledge_base(meta: dict[str, str], dry_run: bool, source_statuses: dict[str, dict[str, object]]) -> None:
    print(f"将更新长期知识库：{KNOWLEDGE_BASE}")
    if dry_run:
        print("[dry-run] 不会实际更新长期知识库。")
        return

    ensure_knowledge_base_exists()
    existing = KNOWLEDGE_BASE.read_text(encoding="utf-8")
    updated = update_knowledge_base_text(existing, meta, source_statuses)
    KNOWLEDGE_BASE.write_text(updated, encoding="utf-8", newline="\n")
    print("已更新长期知识库最近一次自动化运行记录。")


def main() -> int:
    parser = argparse.ArgumentParser(description="生成 Starlink 情报周报自动化测试文档。")
    parser.add_argument("--no-email", action="store_true", help="只生成 Markdown，不发送邮件。")
    parser.add_argument("--dry-run", action="store_true", help="打印将要执行的操作，不写文件、不发邮件。")
    parser.add_argument("--no-collect", action="store_true", help="不执行真实来源采集，只生成周报。")
    parser.add_argument(
        "--max-history-records",
        type=int,
        default=20,
        help="本周周报中自动化测试记录最多保留的条数，默认 20。",
    )
    parser.add_argument(
        "--max-source-items",
        type=int,
        default=10,
        help="周报中最多展示的真实来源记录数，默认 10。",
    )
    args = parser.parse_args()

    if args.max_history_records < 1:
        print("--max-history-records 必须是大于等于 1 的整数。")
        return 2
    if args.max_source_items < 1:
        print("--max-source-items 必须是大于等于 1 的整数。")
        return 2

    send_email_enabled = not args.no_email and not args.dry_run
    collect_enabled = not args.no_collect
    meta = get_run_metadata(send_email_enabled, collect_enabled)
    weekly_path = WEEKLY_DIR / f"{meta['iso_week']}.md"
    collection_result = None
    collection_errors: list[str] = []
    source_items: list[dict[str, object]] = []
    source_statuses: dict[str, dict[str, object]] = {}

    print("开始执行 Starlink 情报周报自动化测试。")
    print(f"项目根目录：{PROJECT_ROOT}")
    print(f"当前 ISO 周编号：{meta['iso_week']}")
    print(f"是否发送邮件：{meta['send_email']}")
    print(f"是否执行真实来源采集：{meta['collect_sources']}")

    print(f"自动化测试记录最多保留：{args.max_history_records} 条")
    print(f"周报真实来源记录最多展示：{args.max_source_items} 条")
    meta["max_source_items"] = str(args.max_source_items)

    if args.no_collect:
        print("已按 --no-collect 参数跳过真实来源采集。")
        source_statuses = load_statuses_for_report()
        apply_status_to_meta(meta, source_statuses)
        source_items = latest_items_for_report(args.max_source_items, source_statuses)
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
        apply_status_to_meta(meta, source_statuses)
        source_items = collection_result.items or latest_items_for_report(args.max_source_items)

    write_weekly_file(
        weekly_path=weekly_path,
        meta=meta,
        dry_run=args.dry_run,
        max_records=args.max_history_records,
        source_items=source_items,
        collection_errors=collection_errors,
        source_statuses=source_statuses,
    )
    update_knowledge_base(meta, args.dry_run, source_statuses)

    if args.dry_run:
        print("[dry-run] 已完成演练，不会发送邮件。")
        print(f"[dry-run] 本次将生成或更新的周报路径：{weekly_path}")
        print(f"[dry-run] 本次将更新的知识库路径：{KNOWLEDGE_BASE}")
        return 0

    if args.no_email:
        print("已按 --no-email 参数跳过邮件发送。")
        print(f"本次生成或更新的周报路径：{weekly_path}")
        print(f"本次更新的知识库路径：{KNOWLEDGE_BASE}")
        return 0

    print("开始发送邮件。")
    collection_context = {
        "collected": meta["collect_sources"],
        "source_names": meta["source_names"],
        "item_count": meta["source_item_count"],
        "health_status": meta["health_status"],
        "page_change_status": meta["page_change_status"],
        "new_items": meta["new_items"],
        "changed_items": meta["changed_items"],
        "unchanged_items": meta["unchanged_items"],
        "attachment": str(weekly_path),
        "connected_source_count": meta["connected_source_count"],
        "source_overview": meta["source_overview"],
    }
    if not send_weekly_email(weekly_path, meta["iso_week"], collection_context=collection_context):
        return 1

    print("自动化测试流程执行完成。")
    print(f"本次生成或更新的周报路径：{weekly_path}")
    print(f"本次更新的知识库路径：{KNOWLEDGE_BASE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
