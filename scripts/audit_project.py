from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CURRENT_STAGE = "3A"

REQUIRED_FILES = [
    "README.md",
    "requirements.txt",
    ".env.example",
    ".gitignore",
    "sources.yml",
    ".github/workflows/weekly.yml",
    "scripts/run_weekly.py",
    "scripts/collect_sources.py",
    "scripts/send_email.py",
    "scripts/validate_env.py",
    "scripts/self_check.py",
    "scripts/print_action_summary.py",
    "scripts/check_outputs.py",
    "scripts/audit_project.py",
    "scripts/llm_summarize.py",
    "docs/starlink_knowledge_base.md",
    "docs/deployment_checklist.md",
    "docs/operations_guide.md",
    "RELEASE_NOTES.md",
    "weekly/index.md",
    "data/items.jsonl",
    "data/source_status.json",
    "data/extraction_quality.json",
    "data/weekly_manifest.json",
    "data/run_history.jsonl",
    "data/llm_audit.json",
]

GITIGNORE_RULES = [".env", "prompts/", "outputs/logs/*.log", "data/raw/", "data/cache/"]

SENSITIVE_SCAN_TARGETS = [
    "README.md",
    "RELEASE_NOTES.md",
    ".github",
    "scripts",
    "docs",
    "weekly",
    "requirements.txt",
    ".env.example",
    "sources.yml",
    "data/items.jsonl",
    "data/source_status.json",
    "data/extraction_quality.json",
    "data/weekly_manifest.json",
    "data/run_history.jsonl",
    "data/llm_audit.json",
    "data/llm_summaries.json",
]

ALLOWED_PLACEHOLDERS = [
    "SMTP_PASSWORD=your_email_authorization_code",
    "GITEE_REMOTE=https://username:token@gitee.com/username/starlink_intel_weekly.git",
    "GITEE_REMOTE=https://用户名:私人令牌@gitee.com/用户名/仓库名.git",
    "https://username:token@gitee.com/username/starlink_intel_weekly.git",
    "https://用户名:私人令牌@gitee.com/用户名/仓库名.git",
    "OPENAI_API_KEY=your_openai_api_key_here",
    "OPENAI_API_KEY=...",
    "OPENAI_MODEL=your_openai_model_here",
]

FORBIDDEN_SOURCE_HINTS = [
    "wechat",
    "weixin",
    "公众号",
    "arxiv",
    "fcc",
    "celestrak",
    "launchlibrary",
    "nextspaceflight",
    "spaceflightnow",
    "rocketlaunch",
]


def current_week_id() -> str:
    now = datetime.now().astimezone()
    iso = now.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def read_text(relative_path: str) -> str:
    return (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")


def add_issue(report: dict[str, Any], section: str, message: str) -> None:
    report["checks"][section] = "failed"
    report["errors"].append(f"{section}: {message}")


def add_warning(report: dict[str, Any], message: str) -> None:
    report["warnings"].append(message)


def mark_passed_if_clean(report: dict[str, Any], section: str) -> None:
    report["checks"].setdefault(section, "passed")


def check_repo_structure(report: dict[str, Any]) -> None:
    section = "repo_structure"
    missing = [path for path in REQUIRED_FILES if not (PROJECT_ROOT / path).exists()]
    if missing:
        add_issue(report, section, "缺少文件：" + "、".join(missing))
        return
    mark_passed_if_clean(report, section)


def run_git_check_ignore(path: str) -> bool | None:
    try:
        result = subprocess.run(
            ["git", "check-ignore", "-v", path],
            cwd=PROJECT_ROOT,
            text=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    except OSError:
        return None
    return result.returncode == 0


def check_gitignore(report: dict[str, Any]) -> None:
    section = "gitignore"
    gitignore_path = PROJECT_ROOT / ".gitignore"
    if not gitignore_path.exists():
        add_issue(report, section, ".gitignore 不存在")
        return
    lines = {line.strip() for line in gitignore_path.read_text(encoding="utf-8").splitlines()}
    missing = [rule for rule in GITIGNORE_RULES if rule not in lines]
    if missing:
        add_issue(report, section, "缺少规则：" + "、".join(missing))
        return

    for ignored_path in [".env", "prompts/"]:
        ignored = run_git_check_ignore(ignored_path)
        if ignored is False:
            add_issue(report, section, f"{ignored_path} 未被 git check-ignore 忽略")
            return
        if ignored is None:
            add_warning(report, "无法执行 git check-ignore，已完成 .gitignore 静态规则检查。")
    mark_passed_if_clean(report, section)


def check_workflow(report: dict[str, Any]) -> None:
    section = "workflow"
    path = PROJECT_ROOT / ".github/workflows/weekly.yml"
    if not path.exists():
        add_issue(report, section, "workflow 文件不存在")
        return
    text = path.read_text(encoding="utf-8")
    try:
        yaml.safe_load(text)
    except yaml.YAMLError as exc:
        add_issue(report, section, f"workflow YAML 无法解析：{exc.__class__.__name__}")
        return
    required_snippets = [
        "name: Starlink Weekly Automation",
        "run-name: Starlink Weekly Automation",
        "workflow_dispatch:",
        "schedule:",
        'cron: "17 0 * * 1"',
        "permissions:",
        "contents: write",
        "concurrency:",
        "python scripts/run_weekly.py --output-mode dual --max-source-items 10 --max-history-records 20",
        "python scripts/check_outputs.py --strict",
        "python scripts/audit_project.py --strict",
        "if: always()",
        "LLM_ENABLED",
        "OPENAI_API_KEY",
        "OPENAI_MODEL",
        'if [ "${LLM_ENABLED}" = "true" ] && [ -n "${OPENAI_API_KEY}" ]; then',
        "--enable-llm",
        "data/llm_audit.json",
    ]
    missing = [snippet for snippet in required_snippets if snippet not in text]
    if missing:
        add_issue(report, section, "workflow 缺少配置：" + "、".join(missing))
        return
    if re.search(r"(?m)^\s+push:\s*$", text):
        add_issue(report, section, "workflow 不应包含 push 触发")
        return
    if re.search(r"(?m)^\s+pull_request:\s*$", text):
        add_issue(report, section, "workflow 不应包含 pull_request 触发")
        return
    if 'echo "$GITEE_REMOTE"' in text or "echo $GITEE_REMOTE" in text:
        add_issue(report, section, "workflow 可能打印完整 GITEE_REMOTE")
        return
    if 'echo "$OPENAI_API_KEY"' in text or "echo $OPENAI_API_KEY" in text:
        add_issue(report, section, "workflow 可能打印 OPENAI_API_KEY")
        return
    if "exit 0" not in text or "GITEE_SYNC_STATUS=failed" not in text:
        add_issue(report, section, "Gitee 同步非阻塞状态不明确")
        return

    deployment_text = ""
    deployment_path = PROJECT_ROOT / "docs/deployment_checklist.md"
    if deployment_path.exists():
        deployment_text = deployment_path.read_text(encoding="utf-8")
    readme_text = read_text("README.md") if (PROJECT_ROOT / "README.md").exists() else ""
    timing_text = f"{readme_text}\n{deployment_text}"
    for required in ["UTC 00:17", "北京时间每周一 08:17", "日本时间每周一 09:17"]:
        if required not in timing_text:
            add_issue(report, section, f"文档缺少定时说明：{required}")
            return
    mark_passed_if_clean(report, section)


def check_sources(report: dict[str, Any]) -> None:
    section = "sources"
    path = PROJECT_ROOT / "sources.yml"
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        add_issue(report, section, f"sources.yml 无法解析：{exc.__class__.__name__}")
        return
    sources = data.get("sources", [])
    if not isinstance(sources, list):
        add_issue(report, section, "sources 必须是列表")
        return
    enabled = [source for source in sources if isinstance(source, dict) and source.get("enabled") is True]
    enabled_ids = {str(source.get("id")) for source in enabled}
    expected_ids = {"starlink_official_updates", "spacex_official_launches"}
    if enabled_ids != expected_ids:
        add_issue(report, section, f"enabled sources 应为 {sorted(expected_ids)}，实际为 {sorted(enabled_ids)}")
        return
    for source in enabled:
        if source.get("source_type") != "official" or source.get("reliability_tier") != "S":
            add_issue(report, section, f"{source.get('id')} 应为 official / S")
            return
    serialized = json.dumps(data, ensure_ascii=False).lower()
    forbidden = [hint for hint in FORBIDDEN_SOURCE_HINTS if hint in serialized]
    if forbidden:
        add_issue(report, section, "sources.yml 出现未允许来源线索：" + "、".join(forbidden))
        return
    mark_passed_if_clean(report, section)


def check_llm_config_docs(report: dict[str, Any]) -> None:
    section = "llm_config"
    env_example = read_text(".env.example") if (PROJECT_ROOT / ".env.example").exists() else ""
    required_env = [
        "LLM_ENABLED=false",
        "OPENAI_API_KEY=your_openai_api_key_here",
        "OPENAI_MODEL=your_openai_model_here",
        "LLM_MAX_ITEMS=10",
        "LLM_STRICT_SOURCE=true",
    ]
    missing_env = [item for item in required_env if item not in env_example]
    if missing_env:
        add_issue(report, section, ".env.example 缺少 LLM 占位符：" + "、".join(missing_env))
        return

    readme = read_text("README.md") if (PROJECT_ROOT / "README.md").exists() else ""
    required_readme = [
        "ChatGPT Plus 订阅不能直接作为 GitHub Actions 中的 OpenAI API 调用额度使用",
        "LLM 默认关闭",
        "OPENAI_API_KEY",
        "无来源不写结论",
        "页面级记录不扩展成具体事实",
        "data/llm_audit.json",
        "data/llm_summaries.json",
    ]
    missing_readme = [item for item in required_readme if item not in readme]
    if missing_readme:
        add_issue(report, section, "README 缺少 LLM 说明：" + "、".join(missing_readme))
        return
    mark_passed_if_clean(report, section)


def json_file(path: Path) -> tuple[bool, Any | None, str | None]:
    if not path.exists():
        return False, None, "文件不存在"
    try:
        return True, json.loads(path.read_text(encoding="utf-8")), None
    except json.JSONDecodeError as exc:
        return False, None, f"JSON 解析失败：line {exc.lineno}"


def jsonl_file(path: Path) -> tuple[bool, list[dict[str, Any]], str | None]:
    if not path.exists():
        return False, [], "文件不存在"
    records: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as file:
            for line_number, line in enumerate(file, start=1):
                stripped = line.strip()
                if not stripped:
                    continue
                value = json.loads(stripped)
                if isinstance(value, dict):
                    records.append(value)
    except json.JSONDecodeError as exc:
        return False, records, f"JSONL 第 {line_number} 行解析失败：{exc.msg}"
    return True, records, None


def check_data_files(report: dict[str, Any]) -> None:
    section = "data_files"
    for relative in ["data/items.jsonl", "data/run_history.jsonl"]:
        valid, records, error = jsonl_file(PROJECT_ROOT / relative)
        if not valid:
            add_issue(report, section, f"{relative} 异常：{error}")
            return
        if relative.endswith("run_history.jsonl") and len(records) > 200:
            add_issue(report, section, "run_history.jsonl 超过 200 行")
            return

    for relative in ["data/source_status.json", "data/extraction_quality.json", "data/weekly_manifest.json", "data/llm_audit.json"]:
        valid, data, error = json_file(PROJECT_ROOT / relative)
        if not valid:
            add_issue(report, section, f"{relative} 异常：{error}")
            return
        sources = data.get("sources", {}) if isinstance(data, dict) else {}
        if relative in {"data/source_status.json", "data/extraction_quality.json"} and len(sources) < 2:
            add_issue(report, section, f"{relative} 至少应包含两个来源")
            return
        if relative == "data/weekly_manifest.json":
            weeks = data.get("weeks", {}) if isinstance(data, dict) else {}
            if current_week_id() not in weeks:
                add_issue(report, section, "weekly_manifest.json 缺少当前周")
                return
        if relative == "data/llm_audit.json":
            status = data.get("llm_status") if isinstance(data, dict) else None
            if not status:
                add_issue(report, section, "llm_audit.json 缺少 llm_status")
                return
            if status == "generated":
                summary_valid, _summary_data, summary_error = json_file(PROJECT_ROOT / "data/llm_summaries.json")
                if not summary_valid:
                    add_issue(report, section, f"llm_status=generated 时 llm_summaries.json 异常：{summary_error}")
                    return
    summary_path = PROJECT_ROOT / "data/llm_summaries.json"
    if summary_path.exists():
        summary_valid, _summary_data, summary_error = json_file(summary_path)
        if not summary_valid:
            add_issue(report, section, f"data/llm_summaries.json 异常：{summary_error}")
            return
    mark_passed_if_clean(report, section)


def check_weekly_outputs(report: dict[str, Any]) -> None:
    section = "weekly_outputs"
    week_id = current_week_id()
    paths = {
        "summary": PROJECT_ROOT / "weekly" / f"{week_id}-summary.md",
        "details": PROJECT_ROOT / "weekly" / f"{week_id}-details.md",
        "index": PROJECT_ROOT / "weekly" / f"{week_id}.md",
        "weekly_index": PROJECT_ROOT / "weekly/index.md",
    }
    missing = [name for name, path in paths.items() if not path.exists()]
    if missing:
        add_issue(report, section, "缺少 weekly 输出：" + "、".join(missing))
        return
    summary = paths["summary"].read_text(encoding="utf-8")
    details = paths["details"].read_text(encoding="utf-8")
    index = paths["index"].read_text(encoding="utf-8")
    weekly_index = paths["weekly_index"].read_text(encoding="utf-8")
    for required in ["本周核心结论", "来源状态概览", "解析质量概览"]:
        if required not in summary:
            add_issue(report, section, f"summary 缺少：{required}")
            return
    if "大模型辅助摘要" not in summary:
        add_issue(report, section, "summary 缺少：大模型辅助摘要")
        return
    for required in ["来源状态诊断", "解析质量诊断", "采集条目明细"]:
        if required not in details:
            add_issue(report, section, f"details 缺少：{required}")
            return
    if "大模型摘要审计" not in details:
        add_issue(report, section, "details 缺少：大模型摘要审计")
        return
    if f"./{week_id}-summary.md" not in index or f"./{week_id}-details.md" not in index:
        add_issue(report, section, "兼容索引缺少 summary/details 相对链接")
        return
    if week_id not in weekly_index:
        add_issue(report, section, "weekly/index.md 缺少当前周编号")
        return
    mark_passed_if_clean(report, section)


def check_email_attachments(report: dict[str, Any]) -> None:
    section = "email_attachments"
    send_email = read_text("scripts/send_email.py")
    run_weekly = read_text("scripts/run_weekly.py")
    required = [
        "attachment_paths",
        "attachments = [Path",
        "for attachment in attachments",
        "summary_file",
        "details_file",
    ]
    missing = [item for item in required if item not in f"{send_email}\n{run_weekly}"]
    if missing:
        add_issue(report, section, "邮件多附件能力缺少线索：" + "、".join(missing))
        return
    forbidden = [".env", "data/raw", "data/cache"]
    attachment_related = "\n".join(line for line in run_weekly.splitlines() if "attachment" in line or "send_weekly_email" in line)
    if any(item in attachment_related for item in forbidden):
        add_issue(report, section, "邮件附件逻辑疑似包含禁止路径")
        return
    mark_passed_if_clean(report, section)


def iter_scan_files() -> list[Path]:
    files: list[Path] = []
    for target in SENSITIVE_SCAN_TARGETS:
        path = PROJECT_ROOT / target
        if not path.exists():
            continue
        if path.is_file():
            files.append(path)
            continue
        files.extend(
            item
            for item in path.rglob("*")
            if item.is_file() and "__pycache__" not in item.parts and item.suffix != ".pyc"
        )
    return sorted(set(files))


def sanitized_text(path: Path) -> str:
    text = path.read_text(encoding="utf-8", errors="ignore")
    for placeholder in ALLOWED_PLACEHOLDERS:
        text = text.replace(placeholder, "")
    return text


def check_secret_scan(report: dict[str, Any]) -> None:
    section = "secret_scan"
    issues: list[str] = []
    for path in iter_scan_files():
        relative = path.relative_to(PROJECT_ROOT).as_posix()
        if relative == ".env" or relative.startswith("prompts/"):
            issues.append(f"{relative}: forbidden_file")
            continue
        text = sanitized_text(path)
        checks = [
            (r"SMTP_PASSWORD\s*=\s*[^\s$#][^\n\r]*", "smtp_password_value"),
            (r"https://[^\s/:]+:[^\s@]+@gitee\.com", "gitee_remote_with_token"),
            (r"ghp_[A-Za-z0-9_]{20,}", "github_pat_legacy"),
            (r"github_pat_[A-Za-z0-9_]{20,}", "github_pat"),
            (r"sk-[A-Za-z0-9_\-]{20,}", "openai_api_key"),
            (r"OPENAI_API_KEY\s*=\s*(?!your_openai_api_key_here|\.\.\.)[^\s$#][^\n\r]*", "openai_api_key_value"),
            (r"(?i)(private\s*token|私人令牌)\s*[:=]\s*[A-Za-z0-9_\-]{16,}", "private_token"),
            (r"(?i)(authorization[_ -]?code|授权码)\s*[:=]\s*[A-Za-z0-9_\-]{16,}", "smtp_auth_code"),
        ]
        for pattern, issue_type in checks:
            if re.search(pattern, text):
                issues.append(f"{relative}: {issue_type}")
    if issues:
        add_issue(report, section, "疑似敏感信息：" + "、".join(sorted(set(issues))))
        return
    mark_passed_if_clean(report, section)


def build_report() -> dict[str, Any]:
    report: dict[str, Any] = {
        "status": "unknown",
        "stage": CURRENT_STAGE,
        "checks": {},
        "errors": [],
        "warnings": [],
    }
    check_repo_structure(report)
    check_gitignore(report)
    check_workflow(report)
    check_sources(report)
    check_llm_config_docs(report)
    check_data_files(report)
    check_weekly_outputs(report)
    check_email_attachments(report)
    check_secret_scan(report)
    report["status"] = "passed" if not report["errors"] else "failed"
    return report


def print_text_report(report: dict[str, Any]) -> None:
    print("开始项目稳定性与配置审计。")
    names = [
        ("repo_structure", "仓库结构"),
        ("gitignore", ".gitignore"),
        ("workflow", "GitHub Actions"),
        ("sources", "sources.yml"),
        ("llm_config", "LLM 配置与文档"),
        ("data_files", "数据文件"),
        ("weekly_outputs", "weekly 输出"),
        ("email_attachments", "邮件附件能力"),
        ("secret_scan", "敏感信息扫描"),
    ]
    for key, label in names:
        print(f"{label}：{report['checks'].get(key, 'unknown')}")
    if report["warnings"]:
        print("审计警告：")
        for warning in report["warnings"]:
            print(f"- {warning}")
    if report["errors"]:
        print("审计错误：")
        for error in report["errors"]:
            print(f"- {error}")
    print(f"审计完成：{report['status']}")


def main() -> int:
    parser = argparse.ArgumentParser(description="执行项目稳定性与配置审计。")
    parser.add_argument("--strict", action="store_true", help="严格模式：关键检查失败时返回非 0。")
    parser.add_argument("--json", action="store_true", help="输出 JSON 格式审计报告。")
    args = parser.parse_args()

    report = build_report()
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print_text_report(report)
    if args.strict and report["status"] != "passed":
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
