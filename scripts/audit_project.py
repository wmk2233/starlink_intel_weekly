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
CURRENT_STAGE = "4B.1"

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
    "scripts/diagnose_official_pages.py",
    "scripts/diagnose_official_details.py",
    "scripts/parsers/__init__.py",
    "scripts/parsers/common.py",
    "scripts/parsers/starlink_updates.py",
    "scripts/parsers/spacex_launches.py",
    "tests/test_official_item_parsers.py",
    "tests/test_item_baseline_merge.py",
    "tests/test_item_quality.py",
    "tests/test_detail_static_parsing.py",
    "tests/test_detail_render_fallback.py",
    "tests/test_detail_failure_recovery.py",
    "tests/test_parser_upgrade_semantics.py",
    "tests/test_dynamic_report_wording.py",
    "tests/test_llm_dedup.py",
    "tests/test_llm_guardrails.py",
    "tests/test_llm_reference_alignment.py",
    "docs/starlink_knowledge_base.md",
    "docs/deployment_checklist.md",
    "docs/operations_guide.md",
    "docs/parser_reconnaissance.md",
    "RELEASE_NOTES.md",
    "weekly/index.md",
    "data/items.jsonl",
    "data/source_status.json",
    "data/extraction_quality.json",
    "data/item_extraction_state.json",
    "data/item_extraction_report.json",
    "data/detail_extraction_diagnostics.json",
    "data/weekly_manifest.json",
    "data/run_history.jsonl",
    "data/llm_audit.json",
    "data/llm_usage.jsonl",
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
    "data/item_extraction_state.json",
    "data/item_extraction_report.json",
    "data/detail_extraction_diagnostics.json",
    "data/weekly_manifest.json",
    "data/run_history.jsonl",
    "data/llm_audit.json",
    "data/llm_summaries.json",
    "data/llm_usage.jsonl",
    "tests",
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
    "DEEPSEEK_API_KEY=your_deepseek_api_key_here",
    "DEEPSEEK_API_KEY=...",
    "DEEPSEEK_API_KEY=<真实 API Key>",
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
    for tracked_output in ["data/llm_audit.json", "data/llm_summaries.json", "data/llm_usage.jsonl"]:
        ignored = run_git_check_ignore(tracked_output)
        if ignored is True:
            add_issue(report, section, f"{tracked_output} 不应被忽略")
            return
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
        "LLM_PROVIDER",
        "OPENAI_API_KEY",
        "OPENAI_MODEL",
        "DEEPSEEK_API_KEY",
        "DEEPSEEK_MODEL",
        "DEEPSEEK_BASE_URL",
        'if [ "${LLM_ENABLED}" = "true" ]; then',
        '--enable-llm --llm-provider deepseek',
        '--enable-llm --llm-provider openai',
        "skipped_no_api_key",
        "--enable-llm",
        "data/llm_audit.json",
        "data/llm_usage.jsonl",
        "actions/checkout@v5",
        "actions/setup-python@v6",
        "python -m playwright install --with-deps chromium",
        'python -m unittest discover -s tests -p "test_*.py" -v',
        "data/item_extraction_state.json",
        "data/item_extraction_report.json",
        "data/detail_extraction_diagnostics.json",
        "DETAIL_RENDER_MODE: ${{ vars.DETAIL_RENDER_MODE || 'auto' }}",
        "MAX_RENDERED_DETAILS_PER_SOURCE: ${{ vars.MAX_RENDERED_DETAILS_PER_SOURCE || '10' }}",
        "LLM_ENABLED: ${{ vars.LLM_ENABLED || 'false' }}",
        "LLM_PROVIDER: ${{ vars.LLM_PROVIDER || 'deepseek' }}",
        "DEEPSEEK_MODEL: ${{ vars.DEEPSEEK_MODEL || 'deepseek-v4-flash' }}",
        "DEEPSEEK_BASE_URL: ${{ vars.DEEPSEEK_BASE_URL || 'https://api.deepseek.com' }}",
        "DEEPSEEK_API_KEY: ${{ secrets.DEEPSEEK_API_KEY }}",
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
    if "actions/checkout@v4" in text or "actions/setup-python@v5" in text:
        add_issue(report, section, "workflow 仍使用旧版 checkout@v4 或 setup-python@v5")
        return
    for variable in [
        "LLM_ENABLED", "LLM_PROVIDER", "DEEPSEEK_MODEL", "DEEPSEEK_BASE_URL", "OPENAI_MODEL",
        "DETAIL_RENDER_MODE", "MAX_RENDERED_DETAILS_PER_SOURCE", "DETAIL_TIMEOUT_MS",
        "DETAIL_WAIT_MS", "DETAIL_MAX_SCROLLS", "DETAIL_CONCURRENCY",
    ]:
        if f"secrets.{variable}" in text:
            add_issue(report, section, f"非敏感配置 {variable} 不应从 Secrets 读取")
            return
    if 'echo "$GITEE_REMOTE"' in text or "echo $GITEE_REMOTE" in text:
        add_issue(report, section, "workflow 可能打印完整 GITEE_REMOTE")
        return
    if 'echo "$OPENAI_API_KEY"' in text or "echo $OPENAI_API_KEY" in text:
        add_issue(report, section, "workflow 可能打印 OPENAI_API_KEY")
        return
    if 'echo "$DEEPSEEK_API_KEY"' in text or "echo $DEEPSEEK_API_KEY" in text:
        add_issue(report, section, "workflow 可能打印 DEEPSEEK_API_KEY")
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


def check_phase4b_detail_extraction(report: dict[str, Any]) -> None:
    section = "phase4b_detail_extraction"
    common = read_text("scripts/parsers/common.py")
    starlink = read_text("scripts/parsers/starlink_updates.py")
    spacex = read_text("scripts/parsers/spacex_launches.py")
    collector = read_text("scripts/collect_sources.py")
    llm = read_text("scripts/llm_summarize.py")
    weekly = read_text("scripts/run_weekly.py")
    diagnostics = read_text("scripts/diagnose_official_details.py")
    workflow = read_text(".github/workflows/weekly.yml")
    required = {
        "common": [
            "DETAIL_ERROR_TYPES", "detect_javascript_shell", "merge_static_and_rendered_fields",
            "semantic_content_hash", "extraction_hash", "detail_page_hash",
        ],
        "starlink": ["starlink_updates_item_v2", "official_update", "starlink_update", "modified_at"],
        "spacex": ["spacex_launches_item_v2", "starlink_relevance", "incidental", "not_direct", "mission_status"],
        "collector": [
            "detail_render_mode", "render_detail_candidates", "detail_timeout_ms", "page_level_fallback",
            "current_run_data_reused", "consecutive_failures", "reused_previous_success",
            "extraction_change_status", "semantic_content_changed", "parser_enrichment",
            "DETAIL_EXTRACTION_DIAGNOSTICS_FILE",
        ],
        "llm": [
            "sources_with_item_level", 'item.get("starlink_relevance") != "direct"',
            "current_run_data_reused=true", "final_core_input_records", "reused_historical_records",
            "allowed_reference_pairs", "final_core_records", "align_llm_references",
            "invalid_record_ids_removed", "missing_urls_repaired", "reference_alignment_status",
        ],
        "weekly": [
            "## 结构化官方条目",
            "## 官方条目解析诊断",
            "## 官方详情页解析诊断",
            "if baseline_count",
            "llm_current_status_text",
            "最终核心输入记录",
        ],
        "diagnostics": ["--render-mode", "--no-write", "final_error_type", "rendered_dom_length"],
        "workflow": ["actions/checkout@v5", "actions/setup-python@v6", "playwright install --with-deps chromium"],
    }
    texts = {
        "common": common, "starlink": starlink, "spacex": spacex, "collector": collector,
        "llm": llm, "weekly": weekly, "diagnostics": diagnostics, "workflow": workflow,
    }
    missing = [f"{name}:{snippet}" for name, snippets in required.items() for snippet in snippets if snippet not in texts[name]]
    if missing:
        add_issue(report, section, "阶段 4B 实现线索缺失：" + "、".join(missing))
        return
    prompt_start = llm.find("def build_user_prompt")
    prompt_end = llm.find("def output_text_from_response", prompt_start)
    prompt_block = llm[prompt_start:prompt_end]
    for forbidden in ['"monitoring_context":', '"source_status":', '"source_based_notes": [']:
        if forbidden in prompt_block:
            add_issue(report, section, f"阶段 4B.1 模型 prompt 不应包含：{forbidden}")
            return
    parser_text = f"{starlink}\n{spacex}"
    for forbidden in ["Last-Modified", "last-modified", "title_from_slug", "date_from_slug"]:
        if forbidden in parser_text:
            add_issue(report, section, f"解析器包含禁止的推断线索：{forbidden}")
            return
    semantic_start = common.find("def semantic_content_hash")
    semantic_end = common.find("def extraction_hash", semantic_start)
    semantic_block = common[semantic_start:semantic_end]
    for forbidden in ["parser_version", "field_evidence", "extraction_confidence", "detail_parse_method"]:
        if forbidden in semantic_block:
            add_issue(report, section, f"semantic_content_hash 不应包含：{forbidden}")
            return
    browser_forbidden = ["page.screenshot(", "record_video_dir", "record_har_path", "tracing.start("]
    if any(snippet in collector for snippet in browser_forbidden):
        add_issue(report, section, "详情浏览器逻辑疑似保存截图、视频、HAR 或 trace")
        return
    source_text = read_text("sources.yml").lower()
    if any(hint in source_text for hint in FORBIDDEN_SOURCE_HINTS):
        add_issue(report, section, "sources.yml 包含搜索引擎或第三方来源线索")
        return
    if "playwright>=1.49.0" not in read_text("requirements.txt"):
        add_issue(report, section, "requirements.txt 缺少 Playwright 依赖")
        return
    docs = "\n".join(
        read_text(path)
        for path in ["README.md", "RELEASE_NOTES.md", "docs/deployment_checklist.md", "docs/operations_guide.md", "docs/parser_reconnaissance.md"]
    )
    for required_doc in [
        "baseline", "page-level fallback", "item-level", "Playwright",
        "detail_extraction_diagnostics.json", "semantic", "历史", "HTML", "HAR", "最终核心输入",
        "allowed_reference_pairs", "source_based_notes", "引用对齐",
    ]:
        if required_doc not in docs:
            add_issue(report, section, f"阶段 4B 文档缺少：{required_doc}")
            return
    mark_passed_if_clean(report, section)


def check_llm_config_docs(report: dict[str, Any]) -> None:
    section = "llm_config"
    env_example = read_text(".env.example") if (PROJECT_ROOT / ".env.example").exists() else ""
    required_env = [
        "LLM_ENABLED=false",
        "LLM_PROVIDER=deepseek",
        "OPENAI_API_KEY=your_openai_api_key_here",
        "OPENAI_MODEL=your_openai_model_here",
        "DEEPSEEK_API_KEY=your_deepseek_api_key_here",
        "DEEPSEEK_BASE_URL=https://api.deepseek.com",
        "DEEPSEEK_MODEL=deepseek-v4-flash",
        "LLM_MAX_ITEMS=10",
        "LLM_STRICT_SOURCE=true",
        "LLM_MAX_USAGE_RECORDS=200",
    ]
    missing_env = [item for item in required_env if item not in env_example]
    if missing_env:
        add_issue(report, section, ".env.example 缺少 LLM 占位符：" + "、".join(missing_env))
        return

    readme = read_text("README.md") if (PROJECT_ROOT / "README.md").exists() else ""
    required_readme = [
        "ChatGPT Plus 订阅不能直接作为 GitHub Actions 中的 OpenAI API 调用额度使用",
        "LLM 默认关闭",
        "支持 DeepSeek provider",
        "DeepSeek API Key 需要单独",
        "API Key 不得提交",
        "LLM_PROVIDER",
        "DEEPSEEK_API_KEY",
        "OPENAI_API_KEY",
        "无来源不写结论",
        "页面级记录不扩展成具体事实",
        "data/llm_audit.json",
        "data/llm_summaries.json",
        "data/llm_usage.jsonl",
        "GitHub Variables",
        "GitHub Secrets",
        "source_id + normalized_url",
        "页面 changed",
        "条目 changed",
        "actions/checkout@v5",
        "actions/setup-python@v6",
    ]
    missing_readme = [item for item in required_readme if item not in readme]
    if missing_readme:
        add_issue(report, section, "README 缺少 LLM 说明：" + "、".join(missing_readme))
        return

    deployment = read_text("docs/deployment_checklist.md") if (PROJECT_ROOT / "docs/deployment_checklist.md").exists() else ""
    required_deployment = [
        "LLM_ENABLED",
        "LLM_PROVIDER",
        "DEEPSEEK_API_KEY",
        "DEEPSEEK_MODEL",
        "GitHub Variables",
        "GitHub Secrets",
        "actions/checkout@v5",
        "actions/setup-python@v6",
    ]
    missing_deployment = [item for item in required_deployment if item not in deployment]
    if missing_deployment:
        add_issue(report, section, "部署清单缺少 DeepSeek Secrets：" + "、".join(missing_deployment))
        return

    llm_script = read_text("scripts/llm_summarize.py")
    legacy_default_patterns = [
        r'DEFAULT_DEEPSEEK_MODEL\s*=\s*["\']deepseek-chat["\']',
        r'DEFAULT_DEEPSEEK_MODEL\s*=\s*["\']deepseek-reasoner["\']',
    ]
    if any(re.search(pattern, llm_script) for pattern in legacy_default_patterns):
        add_issue(report, section, "旧 DeepSeek 模型名不应作为默认模型")
        return
    for required_function in ["deduplicate_llm_input_records", "normalize_and_deduplicate_llm_references"]:
        if f"def {required_function}" not in llm_script:
            add_issue(report, section, f"llm_summarize.py 缺少 {required_function}")
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
    for relative in ["data/items.jsonl", "data/run_history.jsonl", "data/llm_usage.jsonl"]:
        valid, records, error = jsonl_file(PROJECT_ROOT / relative)
        if not valid:
            add_issue(report, section, f"{relative} 异常：{error}")
            return
        if relative.endswith("run_history.jsonl") and len(records) > 200:
            add_issue(report, section, "run_history.jsonl 超过 200 行")
            return
        if relative.endswith("llm_usage.jsonl"):
            if len(records) > 200:
                add_issue(report, section, "llm_usage.jsonl 超过 200 行")
                return
            for record in records:
                required_fields = {
                    "generated_at",
                    "week_id",
                    "llm_enabled",
                    "api_called",
                    "provider",
                    "model",
                    "status",
                    "validation_status",
                    "input_records_before_dedup",
                    "input_records_after_dedup",
                    "prompt_tokens",
                    "completion_tokens",
                    "total_tokens",
                    "latency_ms",
                    "error_type",
                }
                if not required_fields <= set(record):
                    add_issue(report, section, "llm_usage.jsonl 存在缺失字段")
                    return
                total_tokens = record.get("total_tokens")
                latency_ms = record.get("latency_ms")
                if total_tokens is not None and (not isinstance(total_tokens, int) or isinstance(total_tokens, bool) or total_tokens < 0):
                    add_issue(report, section, "llm_usage.jsonl 的 total_tokens 必须为 null 或非负整数")
                    return
                if latency_ms is not None and (not isinstance(latency_ms, (int, float)) or isinstance(latency_ms, bool) or latency_ms < 0):
                    add_issue(report, section, "llm_usage.jsonl 的 latency_ms 必须为 null 或非负数")
                    return
            phase4b_fields = {
                "raw_candidate_records", "records_after_url_dedup", "final_core_input_records",
                "final_core_unique_urls", "reused_historical_records",
                "invalid_record_ids_removed", "invalid_urls_removed", "missing_record_ids_repaired",
                "missing_urls_repaired", "key_points_removed_without_sources", "reference_alignment_status",
            }
            if not records or not phase4b_fields <= set(records[-1]):
                add_issue(report, section, "最新 llm_usage.jsonl 记录缺少 Phase 4B 输入统计")
                return

    for relative in [
        "data/source_status.json",
        "data/extraction_quality.json",
        "data/item_extraction_state.json",
        "data/item_extraction_report.json",
        "data/detail_extraction_diagnostics.json",
        "data/weekly_manifest.json",
        "data/llm_audit.json",
    ]:
        valid, data, error = json_file(PROJECT_ROOT / relative)
        if not valid:
            add_issue(report, section, f"{relative} 异常：{error}")
            return
        sources = data.get("sources", {}) if isinstance(data, dict) else {}
        if relative in {
            "data/source_status.json",
            "data/extraction_quality.json",
            "data/item_extraction_state.json",
            "data/item_extraction_report.json",
            "data/detail_extraction_diagnostics.json",
        } and len(sources) < 2:
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
            if not data.get("llm_provider"):
                add_issue(report, section, "llm_audit.json 缺少 llm_provider")
                return
            if "model" not in data:
                add_issue(report, section, "llm_audit.json 缺少 model 字段")
                return
            if not data.get("base_url_label"):
                add_issue(report, section, "llm_audit.json 缺少 base_url_label")
                return
            before = data.get("input_records_before_dedup")
            after = data.get("input_records_after_dedup")
            removed = data.get("duplicate_records_removed")
            if not all(isinstance(value, int) and not isinstance(value, bool) for value in [before, after, removed]):
                add_issue(report, section, "llm_audit.json 缺少有效去重计数")
                return
            if not (0 <= after <= before and removed == before - after):
                add_issue(report, section, "llm_audit.json 去重计数不一致")
                return
            final_core = data.get("final_core_input_records")
            after_url = data.get("records_after_url_dedup")
            if not isinstance(final_core, int) or not isinstance(after_url, int) or not 0 <= final_core <= after_url:
                add_issue(report, section, "llm_audit.json 缺少有效最终核心输入统计")
                return
            alignment_count_fields = {
                "invalid_record_ids_removed", "invalid_urls_removed", "missing_record_ids_repaired",
                "missing_urls_repaired", "key_points_removed_without_sources",
            }
            if not all(
                isinstance(data.get(field), int)
                and not isinstance(data.get(field), bool)
                and data.get(field) >= 0
                for field in alignment_count_fields
            ):
                add_issue(report, section, "llm_audit.json 缺少有效引用对齐计数")
                return
            if data.get("reference_alignment_status") not in {"not_run", "passed", "repaired", "failed"}:
                add_issue(report, section, "llm_audit.json 缺少有效 reference_alignment_status")
                return
            if status == "generated":
                summary_valid, _summary_data, summary_error = json_file(PROJECT_ROOT / "data/llm_summaries.json")
                if not summary_valid:
                    add_issue(report, section, f"llm_status=generated 时 llm_summaries.json 异常：{summary_error}")
                    return
        if relative == "data/item_extraction_state.json":
            for source_id, state in sources.items():
                if not isinstance(state, dict) or not isinstance(state.get("bootstrap_completed"), bool):
                    add_issue(report, section, f"{source_id} 缺少有效 bootstrap_completed")
                    return
        if relative == "data/item_extraction_report.json":
            required = {
                "parser_version", "candidate_count", "detail_fetch_success", "detail_fetch_failed",
                "baseline_items", "new_items", "changed_items", "unchanged_items", "page_level_fallback",
                "candidate_count_total", "static_detail_success", "rendered_detail_attempted",
                "rendered_detail_success", "final_detail_success", "final_detail_failed",
                "final_success_rate", "failure_types", "reused_previous_success",
            }
            for source_id, item_report in sources.items():
                if not isinstance(item_report, dict) or not required <= set(item_report):
                    add_issue(report, section, f"{source_id} 的条目抽取报告字段不完整")
                    return
        if relative == "data/detail_extraction_diagnostics.json":
            allowed_statuses = {"success", "failed", "reused_previous_success"}
            for source_id, source in sources.items():
                if not isinstance(source, dict):
                    add_issue(report, section, f"{source_id} 详情诊断不是 object")
                    return
                for detail in source.get("details", []):
                    if not isinstance(detail, dict) or detail.get("final_status") not in allowed_statuses:
                        add_issue(report, section, f"{source_id} 详情诊断 final_status 非法")
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
    for required in [
        "本周核心结论", "来源状态概览", "解析质量概览", "页面级监测解释",
        "原始候选记录", "最终核心输入记录", "## 结构化官方条目", "### 详情解析情况",
    ]:
        if required not in summary:
            add_issue(report, section, f"summary 缺少：{required}")
            return
    if "大模型辅助摘要" not in summary:
        add_issue(report, section, "summary 缺少：大模型辅助摘要")
        return
    for required in [
        "来源状态诊断", "解析质量诊断", "采集条目明细", "页面级监测解释",
        "原始候选记录", "最终核心输入记录", "## 官方条目解析诊断",
        "## 官方详情页解析诊断", "### 详情失败类型",
    ]:
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
        "官方条目抽取情况",
        "官方详情解析情况",
        "最终核心输入记录",
        "if baseline_count > 0",
        "baseline",
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
            (r"DEEPSEEK_API_KEY\s*=\s*(?!your_deepseek_api_key_here|\.\.\.)[^\s$#][^\n\r]*", "deepseek_api_key_value"),
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
    check_phase4b_detail_extraction(report)
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
        ("phase4b_detail_extraction", "Phase 4B 详情解析与失败恢复"),
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
