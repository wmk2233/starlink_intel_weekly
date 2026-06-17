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


def _source_status() -> dict[str, object]:
    if not SOURCE_STATUS_FILE.exists():
        return {
            "exists": False,
            "health_status": "unknown",
            "change_status": "unknown",
            "new_items": 0,
            "changed_items": 0,
            "unchanged_items": 0,
        }

    try:
        data = json.loads(SOURCE_STATUS_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {
            "exists": True,
            "health_status": "无法解析",
            "change_status": "无法解析",
            "new_items": 0,
            "changed_items": 0,
            "unchanged_items": 0,
        }

    source = data.get("sources", {}).get("starlink_official_updates", {})
    return {
        "exists": True,
        "health_status": source.get("health_status", "unknown"),
        "change_status": source.get("change_status", "unknown"),
        "new_items": source.get("new_items", 0),
        "changed_items": source.get("changed_items", 0),
        "unchanged_items": source.get("unchanged_items", 0),
    }


def main() -> int:
    status = _source_status()
    gitee_configured = bool(os.getenv("GITEE_REMOTE", "").strip())
    gitee_sync_status = os.getenv("GITEE_SYNC_STATUS", "unknown").strip() or "unknown"

    lines = [
        "## Starlink Weekly Automation",
        "",
        "- 阶段：2B",
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
        f"- source_status.json 是否存在：{_yes_no(bool(status['exists']))}",
        f"- 来源健康状态：{status['health_status']}",
        f"- 页面变化状态：{status['change_status']}",
        f"- 新增条目数：{status['new_items']}",
        f"- 变化条目数：{status['changed_items']}",
        f"- 未变化条目数：{status['unchanged_items']}",
        f"- Gitee 同步是否配置：{_yes_no(gitee_configured)}",
        f"- Gitee 同步状态：{gitee_sync_status}",
    ]
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
