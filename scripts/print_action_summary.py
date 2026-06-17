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


def _yes_no(value: bool) -> str:
    return "是" if value else "否"


def _escape_table_cell(value: object) -> str:
    return str(value if value is not None else "").replace("\n", " ").replace("\r", " ").replace("|", "\\|")


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


def _week_id() -> str:
    now = datetime.now().astimezone()
    iso = now.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def main() -> int:
    status_exists, statuses = _source_statuses()
    quality_exists, quality_sources = _extraction_quality()
    gitee_configured = bool(os.getenv("GITEE_REMOTE", "").strip())
    gitee_sync_status = os.getenv("GITEE_SYNC_STATUS", "unknown").strip() or "unknown"
    week_id = _week_id()

    lines = [
        "## Starlink Weekly Automation",
        "",
        "- 阶段：2E",
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
        "- sources.yml 路径：sources.yml",
        f"- items.jsonl 是否存在：{_yes_no(ITEMS_FILE.exists())}",
        f"- source_status.json 是否存在：{_yes_no(status_exists)}",
        f"- extraction_quality.json 是否存在：{_yes_no(quality_exists)}",
        f"- Gitee 同步是否配置：{_yes_no(gitee_configured)}",
        f"- Gitee 同步状态：{gitee_sync_status}",
        "",
        "### 本周输出文档",
        "",
        "| 类型 | 路径 |",
        "|---|---|",
        f"| 总结版 | weekly/{week_id}-summary.md |",
        f"| 明细版 | weekly/{week_id}-details.md |",
        f"| 兼容索引 | weekly/{week_id}.md |",
        "",
        "### 来源状态",
        "",
        "| 来源 | 可达性 | 页面变化状态 | 新增 | 变化 | 未变化 |",
        "|---|---|---|---:|---:|---:|",
    ]
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
            "| 来源 | 主导解析层级 | 主导解析质量 | 平均置信度 | 候选链接数 | 解析器版本 |",
            "|---|---|---|---:|---:|---|",
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
                        _escape_table_cell(quality.get("candidate_links_total") or status.get("candidate_links_total") or 0),
                        _escape_table_cell(quality.get("parser_version") or status.get("parser_version") or "unknown"),
                    ]
                )
                + " |"
            )
    else:
        lines.append("| unknown | unknown | unknown | 0 | 0 | unknown |")

    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
