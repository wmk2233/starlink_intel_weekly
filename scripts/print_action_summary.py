from __future__ import annotations

import json
import os
import platform
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ITEMS_FILE = PROJECT_ROOT / "data" / "items.jsonl"
SOURCE_STATUS_FILE = PROJECT_ROOT / "data" / "source_status.json"


def _yes_no(value: bool) -> str:
    return "是" if value else "否"


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


def main() -> int:
    status_exists, statuses = _source_statuses()
    gitee_configured = bool(os.getenv("GITEE_REMOTE", "").strip())
    gitee_sync_status = os.getenv("GITEE_SYNC_STATUS", "unknown").strip() or "unknown"

    lines = [
        "## Starlink Weekly Automation",
        "",
        "- 阶段：2C",
        f"- 工作流名称：{os.getenv('GITHUB_WORKFLOW', 'unknown')}",
        f"- 分支：{os.getenv('GITHUB_REF_NAME', 'unknown')}",
        f"- 触发方式：{os.getenv('GITHUB_EVENT_NAME', 'unknown')}",
        f"- Python 版本：{platform.python_version()}",
        f"- 本次运行是否成功：{os.getenv('ACTION_RUN_STATUS', 'unknown')}",
        "- 更新文件路径：docs/starlink_knowledge_base.md、weekly/",
        "- 是否执行真实来源采集：是",
        "- 数据文件路径：data/items.jsonl",
        "- source_status.json 路径：data/source_status.json",
        "- sources.yml 路径：sources.yml",
        f"- items.jsonl 是否存在：{_yes_no(ITEMS_FILE.exists())}",
        f"- source_status.json 是否存在：{_yes_no(status_exists)}",
        "",
        "### 来源状态",
        "",
        "| 来源 | 可达性 | 页面变化状态 | 新增 | 变化 | 未变化 |",
        "|---|---|---:|---:|---:|---:|",
    ]
    if statuses:
        for source_id, status in statuses.items():
            lines.append(
                "| "
                + " | ".join(
                    [
                        str(status.get("source_name") or source_id),
                        str(status.get("health_status", "unknown")),
                        str(status.get("change_status", "unknown")),
                        str(status.get("new_items", 0)),
                        str(status.get("changed_items", 0)),
                        str(status.get("unchanged_items", 0)),
                    ]
                )
                + " |"
            )
    else:
        lines.append("| unknown | unknown | unknown | 0 | 0 | 0 |")

    lines.extend(
        [
        f"- Gitee 同步是否配置：{_yes_no(gitee_configured)}",
        f"- Gitee 同步状态：{gitee_sync_status}",
        ]
    )
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
