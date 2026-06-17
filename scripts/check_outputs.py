from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


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
    weekly_manifest_path = DATA_DIR / "weekly_manifest.json"
    run_history_path = DATA_DIR / "run_history.jsonl"
    llm_audit_path = DATA_DIR / "llm_audit.json"
    llm_summary_path = DATA_DIR / "llm_summaries.json"

    report: dict[str, Any] = {"week_id": week_id, "status": "unknown", "checks": {}, "errors": []}

    add_check(report, "summary_exists", summary_path.exists(), str(summary_path))
    add_check(report, "details_exists", details_path.exists(), str(details_path))
    add_check(report, "index_exists", index_path.exists(), str(index_path))
    add_check(report, "weekly_index_exists", weekly_index_path.exists(), str(weekly_index_path))

    valid, error = valid_jsonl_file(items_path)
    add_check(report, "items_jsonl_valid", valid, error)
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
    llm_status = str(llm_audit.get("llm_status") or "unknown") if valid else "unknown"
    if llm_status == "generated":
        valid_summary, error = valid_json_file(llm_summary_path)
        add_check(report, "llm_summary_valid_when_generated", valid_summary, error)
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

    details_text = read_text(details_path)
    add_check(report, "details_has_source_status", "来源状态诊断" in details_text, "details 缺少“来源状态诊断”")
    add_check(report, "details_has_quality", "解析质量诊断" in details_text, "details 缺少“解析质量诊断”")
    add_check(report, "details_has_items", "采集条目明细" in details_text, "details 缺少“采集条目明细”")
    add_check(report, "details_has_llm_audit", "大模型摘要审计" in details_text, "details 缺少“大模型摘要审计”")

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
