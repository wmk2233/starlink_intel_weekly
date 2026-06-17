from __future__ import annotations

import argparse
import platform
import sys
from datetime import datetime
from pathlib import Path

from send_email import send_weekly_email


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WEEKLY_DIR = PROJECT_ROOT / "weekly"
DOCS_DIR = PROJECT_ROOT / "docs"
KNOWLEDGE_BASE = DOCS_DIR / "starlink_knowledge_base.md"
HISTORY_HEADING = "## 4. 自动化测试记录"
LEGACY_HISTORY_HEADING = "## 自动化测试记录"


def get_run_metadata(send_email_enabled: bool) -> dict[str, str]:
    now = datetime.now().astimezone()
    iso = now.isocalendar()
    week_id = f"{iso.year}-W{iso.week:02d}"
    return {
        "run_time": now.strftime("%Y-%m-%d %H:%M:%S %Z%z"),
        "iso_week": week_id,
        "environment": f"{platform.system()} {platform.release()}",
        "python_version": platform.python_version(),
        "send_email": "是" if send_email_enabled else "否",
    }


def build_weekly_document(meta: dict[str, str]) -> str:
    week_id = meta["iso_week"]
    return f"""# Starlink 情报周报自动化测试：{week_id}

## 1. 本周摘要

这是自动化流程测试文档，用于验证：

- Markdown 文件生成；
- 长期知识库更新；
- 邮件发送；
- GitHub Actions 自动提交；
- Gitee 自动同步。

## 2. 自动化运行信息

- 运行时间：{meta["run_time"]}
- ISO 周编号：{meta["iso_week"]}
- 执行环境：{meta["environment"]}
- Python 版本：{meta["python_version"]}
- 是否发送邮件：{meta["send_email"]}

## 3. 后续计划

后续将逐步接入 Starlink 官方网站、SpaceX Launches、FCC、CelesTrak、arXiv、技术博客和微信公众号白名单等信息来源。

{HISTORY_HEADING}

{render_history_records([meta])}
"""


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
                ]
            )
        )
    return "\n".join(rendered)


def _split_base_and_history(existing: str) -> tuple[str, str]:
    candidates = []
    for heading in (HISTORY_HEADING, LEGACY_HISTORY_HEADING):
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


def update_knowledge_base_text(existing: str, meta: dict[str, str]) -> str:
    heading = "## 最近一次自动化运行记录"
    new_section = f"""{heading}

- 运行时间：{meta["run_time"]}
- ISO 周编号：{meta["iso_week"]}
- 执行环境：{meta["environment"]}
- Python 版本：{meta["python_version"]}
- 是否发送邮件：{meta["send_email"]}
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


def ensure_knowledge_base_exists() -> None:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    if not KNOWLEDGE_BASE.exists():
        KNOWLEDGE_BASE.write_text(
            "# Starlink 技术情报长期知识库\n\n"
            "本文件用于记录 Starlink 技术情报的长期更新内容。\n\n"
            "当前阶段仅用于验证自动化链路，尚未接入真实 Starlink 信息采集、大模型总结和知识库更新功能。\n\n"
            "## 最近一次自动化运行记录\n\n"
            "暂无。\n",
            encoding="utf-8",
        )


def write_weekly_file(weekly_path: Path, meta: dict[str, str], dry_run: bool, max_records: int) -> None:
    if weekly_path.exists():
        print(f"检测到本周周报已存在，将追加并整理自动化测试记录：{weekly_path}")
        if dry_run:
            print(f"[dry-run] 不会实际更新周报内容；最多保留最近 {max_records} 条记录。")
            return
        existing = weekly_path.read_text(encoding="utf-8")
        updated = merge_weekly_history(existing, meta, max_records)
        weekly_path.write_text(updated, encoding="utf-8", newline="\n")
        print(f"已追加自动化测试记录，并限制最多保留最近 {max_records} 条。")
        return

    print(f"将创建本周周报：{weekly_path}")
    if dry_run:
        print("[dry-run] 不会实际创建周报文件。")
        return

    WEEKLY_DIR.mkdir(parents=True, exist_ok=True)
    weekly_path.write_text(build_weekly_document(meta), encoding="utf-8", newline="\n")
    print("已创建本周 Markdown 周报。")


def update_knowledge_base(meta: dict[str, str], dry_run: bool) -> None:
    print(f"将更新长期知识库：{KNOWLEDGE_BASE}")
    if dry_run:
        print("[dry-run] 不会实际更新长期知识库。")
        return

    ensure_knowledge_base_exists()
    existing = KNOWLEDGE_BASE.read_text(encoding="utf-8")
    updated = update_knowledge_base_text(existing, meta)
    KNOWLEDGE_BASE.write_text(updated, encoding="utf-8", newline="\n")
    print("已更新长期知识库最近一次自动化运行记录。")


def main() -> int:
    parser = argparse.ArgumentParser(description="生成 Starlink 情报周报自动化测试文档。")
    parser.add_argument("--no-email", action="store_true", help="只生成 Markdown，不发送邮件。")
    parser.add_argument("--dry-run", action="store_true", help="打印将要执行的操作，不写文件、不发邮件。")
    parser.add_argument(
        "--max-history-records",
        type=int,
        default=20,
        help="本周周报中自动化测试记录最多保留的条数，默认 20。",
    )
    args = parser.parse_args()

    if args.max_history_records < 1:
        print("--max-history-records 必须是大于等于 1 的整数。")
        return 2

    send_email_enabled = not args.no_email and not args.dry_run
    meta = get_run_metadata(send_email_enabled)
    weekly_path = WEEKLY_DIR / f"{meta['iso_week']}.md"

    print("开始执行 Starlink 情报周报自动化测试。")
    print(f"项目根目录：{PROJECT_ROOT}")
    print(f"当前 ISO 周编号：{meta['iso_week']}")
    print(f"是否发送邮件：{meta['send_email']}")

    print(f"自动化测试记录最多保留：{args.max_history_records} 条")

    write_weekly_file(weekly_path, meta, args.dry_run, args.max_history_records)
    update_knowledge_base(meta, args.dry_run)

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
    if not send_weekly_email(weekly_path, meta["iso_week"]):
        return 1

    print("自动化测试流程执行完成。")
    print(f"本次生成或更新的周报路径：{weekly_path}")
    print(f"本次更新的知识库路径：{KNOWLEDGE_BASE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
