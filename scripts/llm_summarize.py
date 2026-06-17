from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
ITEMS_FILE = DATA_DIR / "items.jsonl"
SOURCE_STATUS_FILE = DATA_DIR / "source_status.json"
EXTRACTION_QUALITY_FILE = DATA_DIR / "extraction_quality.json"
WEEKLY_MANIFEST_FILE = DATA_DIR / "weekly_manifest.json"
LLM_SUMMARY_FILE = DATA_DIR / "llm_summaries.json"
LLM_AUDIT_FILE = DATA_DIR / "llm_audit.json"
DEFAULT_MODEL = "gpt-4o-mini"
SUMMARY_VERSION = "llm_source_guarded_v1"

ALLOWED_ITEM_FIELDS = [
    "id",
    "source_id",
    "source_name",
    "source_type",
    "reliability_tier",
    "category",
    "title",
    "url",
    "summary",
    "evidence",
    "change_status",
    "extracted_level",
    "source_quality",
    "extraction_confidence",
    "matched_keywords",
    "candidate_links",
    "extraction_notes",
]

PLACEHOLDER_API_KEYS = {"", "your_openai_api_key_here"}
FACT_EXPANSION_PHRASES = [
    "发射成功",
    "计划发射",
    "任务完成",
    "载荷数量",
    "覆盖范围扩大",
    "服务开通",
    "技术升级",
    "网络容量提升",
]


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def is_truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def is_api_key_configured(value: str | None) -> bool:
    return str(value or "").strip() not in PLACEHOLDER_API_KEYS


def project_path(path_value: str | Path) -> Path:
    path = Path(path_value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def read_items_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as file:
        for line in file:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                value = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                records.append(value)
    return records


def truncate_text(value: object, max_length: int) -> str:
    text = "" if value is None else str(value)
    text = text.replace("\r", " ").replace("\n", " ").strip()
    if len(text) <= max_length:
        return text
    return text[: max_length - 1].rstrip() + "…"


def normalize_candidate_links(value: object) -> list[object]:
    if not isinstance(value, list):
        return []
    normalized: list[object] = []
    for item in value[:5]:
        if isinstance(item, str):
            normalized.append(item)
        elif isinstance(item, dict):
            normalized.append({key: item.get(key) for key in ["title", "url"] if item.get(key)})
    return normalized


def normalize_item(item: dict[str, Any]) -> dict[str, Any]:
    normalized = {field: item.get(field) for field in ALLOWED_ITEM_FIELDS}
    normalized["evidence"] = truncate_text(normalized.get("evidence"), 800)
    normalized["candidate_links"] = normalize_candidate_links(normalized.get("candidate_links"))
    if not isinstance(normalized.get("matched_keywords"), list):
        normalized["matched_keywords"] = []
    return normalized


def select_items(items: list[dict[str, Any]], max_items: int) -> list[dict[str, Any]]:
    priority = {"new": 0, "changed": 1, "unchanged": 2}
    sorted_items = sorted(
        items,
        key=lambda item: (
            priority.get(str(item.get("change_status") or "").lower(), 3),
            str(item.get("last_seen_at") or item.get("fetched_at") or ""),
        ),
    )
    return [normalize_item(item) for item in sorted_items[:max_items]]


def build_guardrails(strict_source: bool) -> dict[str, bool]:
    return {
        "strict_source": strict_source,
        "no_external_knowledge": True,
        "no_unsourced_claims": True,
        "page_level_no_fact_expansion": True,
    }


def build_audit(
    *,
    enabled: bool,
    status: str,
    reason: str,
    model: str | None,
    input_records: int,
    summary_generated: bool,
    validation_status: str,
    strict_source: bool,
    errors: list[str] | None = None,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "generated_at": now_iso(),
        "llm_enabled": enabled,
        "llm_status": status,
        "model": model,
        "reason": reason,
        "summary_generated": summary_generated,
        "input_records": input_records,
        "validation_status": validation_status,
        "errors": errors or [],
        "warnings": warnings or [],
        "guardrails": build_guardrails(strict_source),
    }


def write_json(path: Path, payload: dict[str, Any], dry_run: bool) -> None:
    if dry_run:
        print(f"[dry-run] 不会写入：{path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def system_prompt() -> str:
    return (
        "你是一个来源约束型情报摘要助手。\n"
        "你只能根据输入 JSON 中的字段生成摘要。\n"
        "不得使用外部知识。\n"
        "不得使用模型记忆。\n"
        "不得推测未给出的事实。\n"
        "不得编造发射时间、任务状态、载荷数量、技术细节、商业服务状态。\n"
        "如果记录是 page_level 或 source_quality=low，只能说明页面级监测结果，不得写成具体事件。\n"
        "如果没有 new 或 changed 条目，必须明确写“本周未检测到新增或内容变化条目”。\n"
        "每条摘要必须引用已有 record id 和 URL。\n"
        "输出必须是合法 JSON。"
    )


def build_user_prompt(
    selected_items: list[dict[str, Any]],
    source_status: dict[str, Any],
    extraction_quality: dict[str, Any],
    weekly_manifest: dict[str, Any],
) -> str:
    payload = {
        "instructions": {
            "output_json_schema": {
                "llm_summary_version": SUMMARY_VERSION,
                "overall_summary_cn": "string",
                "key_points": [
                    {
                        "point": "string",
                        "source_record_ids": ["record id"],
                        "source_urls": ["url"],
                        "caveat": "string",
                    }
                ],
                "source_based_notes": [
                    {
                        "source_name": "string",
                        "note": "string",
                        "source_record_ids": ["record id"],
                        "source_urls": ["url"],
                        "extracted_level": "string",
                        "source_quality": "string",
                    }
                ],
                "risk_warnings": ["string"],
                "not_generated_claims": ["string"],
            },
            "format": "只输出 JSON，不要 Markdown，不要代码块。",
            "required_not_generated_claims": [
                "未生成发射时间",
                "未生成任务状态",
                "未生成载荷数量",
                "未生成未在来源中出现的技术判断",
            ],
        },
        "source_constraints": {
            "allowed_record_ids": [item.get("id") for item in selected_items],
            "allowed_urls": [item.get("url") for item in selected_items],
            "no_external_sources": True,
            "page_level_low_records_must_not_be_fact_expanded": True,
        },
        "items": selected_items,
        "source_status": source_status,
        "extraction_quality": extraction_quality,
        "weekly_manifest": weekly_manifest,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)


def output_text_from_response(response: Any) -> str:
    direct_text = getattr(response, "output_text", None)
    if isinstance(direct_text, str) and direct_text.strip():
        return direct_text.strip()
    try:
        output = getattr(response, "output", [])
        parts: list[str] = []
        for item in output:
            for content in getattr(item, "content", []) or []:
                text = getattr(content, "text", None)
                if text:
                    parts.append(str(text))
        if parts:
            return "\n".join(parts).strip()
    except Exception:
        return ""
    return ""


def call_openai(model: str, api_key: str, prompt: str) -> str:
    from openai import OpenAI

    client = OpenAI(api_key=api_key)
    if hasattr(client, "responses"):
        response = client.responses.create(
            model=model,
            instructions=system_prompt(),
            input=prompt,
            max_output_tokens=1200,
        )
        return output_text_from_response(response)

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt()},
            {"role": "user", "content": prompt},
        ],
        response_format={"type": "json_object"},
    )
    return str(response.choices[0].message.content or "").strip()


def narrative_text(summary: dict[str, Any]) -> str:
    parts = [str(summary.get("overall_summary_cn") or "")]
    for point in summary.get("key_points", []) if isinstance(summary.get("key_points"), list) else []:
        if isinstance(point, dict):
            parts.append(str(point.get("point") or ""))
            parts.append(str(point.get("caveat") or ""))
    for note in summary.get("source_based_notes", []) if isinstance(summary.get("source_based_notes"), list) else []:
        if isinstance(note, dict):
            parts.append(str(note.get("note") or ""))
    return "\n".join(parts)


def validate_llm_output(raw_text: str, input_records: list[dict[str, Any]]) -> tuple[bool, dict[str, Any] | None, list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    try:
        summary = json.loads(raw_text)
    except json.JSONDecodeError:
        return False, None, ["LLM 输出不是合法 JSON。"], warnings
    if not isinstance(summary, dict):
        return False, None, ["LLM 输出顶层不是 JSON object。"], warnings

    if summary.get("llm_summary_version") != SUMMARY_VERSION:
        errors.append("llm_summary_version 不符合要求。")
    for key in ["overall_summary_cn", "key_points", "source_based_notes", "risk_warnings", "not_generated_claims"]:
        if key not in summary:
            errors.append(f"缺少字段：{key}")

    valid_ids = {str(item.get("id")) for item in input_records if item.get("id")}
    valid_urls = {str(item.get("url")) for item in input_records if item.get("url")}

    key_points = summary.get("key_points", [])
    if not isinstance(key_points, list):
        errors.append("key_points 不是列表。")
        key_points = []
    for index, point in enumerate(key_points, start=1):
        if not isinstance(point, dict):
            errors.append(f"key_points[{index}] 不是 object。")
            continue
        ids = [str(item) for item in point.get("source_record_ids", []) if item]
        urls = [str(item) for item in point.get("source_urls", []) if item]
        if not ids or not urls:
            errors.append(f"key_points[{index}] 缺少来源记录或 URL。")
        if any(item not in valid_ids for item in ids):
            errors.append(f"key_points[{index}] 出现输入外 record id。")
        if any(item not in valid_urls for item in urls):
            errors.append(f"key_points[{index}] 出现输入外 URL。")

    notes = summary.get("source_based_notes", [])
    if not isinstance(notes, list):
        errors.append("source_based_notes 不是列表。")
        notes = []
    for index, note in enumerate(notes, start=1):
        if not isinstance(note, dict):
            errors.append(f"source_based_notes[{index}] 不是 object。")
            continue
        ids = [str(item) for item in note.get("source_record_ids", []) if item]
        urls = [str(item) for item in note.get("source_urls", []) if item]
        if any(item not in valid_ids for item in ids):
            errors.append(f"source_based_notes[{index}] 出现输入外 record id。")
        if any(item not in valid_urls for item in urls):
            errors.append(f"source_based_notes[{index}] 出现输入外 URL。")

    generated_text = narrative_text(summary)
    if input_records and not any(str(item.get("change_status") or "").lower() in {"new", "changed"} for item in input_records):
        if "本周未检测到新增或内容变化条目" not in generated_text:
            errors.append("未检测到 new/changed 条目时，摘要未明确说明本周无新增或内容变化。")

    if input_records and all(
        str(item.get("extracted_level")) == "page_level" and str(item.get("source_quality")) == "low" for item in input_records
    ):
        for phrase in FACT_EXPANSION_PHRASES:
            if phrase in generated_text:
                errors.append(f"page_level / low 记录疑似被扩展成事实：{phrase}")

    return not errors, summary, errors, warnings


def run_llm_summary(
    *,
    enabled: bool,
    dry_run: bool,
    input_items: str | Path = ITEMS_FILE,
    source_status: str | Path = SOURCE_STATUS_FILE,
    extraction_quality: str | Path = EXTRACTION_QUALITY_FILE,
    output: str | Path = LLM_SUMMARY_FILE,
    audit_output: str | Path = LLM_AUDIT_FILE,
    max_items: int = 10,
    model: str | None = None,
    strict_source: bool = True,
    fail_on_llm_error: bool = False,
) -> tuple[int, dict[str, Any]]:
    effective_enabled = enabled or is_truthy(os.getenv("LLM_ENABLED"))
    selected_model = (model or os.getenv("OPENAI_MODEL") or DEFAULT_MODEL).strip()
    output_path = project_path(output)
    audit_path = project_path(audit_output)

    if not effective_enabled:
        audit = build_audit(
            enabled=False,
            status="skipped",
            reason="LLM is disabled.",
            model=None,
            input_records=0,
            summary_generated=False,
            validation_status="skipped",
            strict_source=strict_source,
        )
        write_json(audit_path, audit, dry_run)
        print("LLM 摘要状态：skipped")
        return 0, audit

    api_key = os.getenv("OPENAI_API_KEY")
    if not is_api_key_configured(api_key):
        audit = build_audit(
            enabled=True,
            status="skipped_no_api_key",
            reason="OPENAI_API_KEY is not configured.",
            model=selected_model,
            input_records=0,
            summary_generated=False,
            validation_status="skipped",
            strict_source=strict_source,
        )
        write_json(audit_path, audit, dry_run)
        print("LLM 摘要状态：skipped_no_api_key")
        return 0, audit

    items = read_items_jsonl(project_path(input_items))
    selected_items = select_items(items, max_items)
    source_status_data = read_json(project_path(source_status))
    extraction_quality_data = read_json(project_path(extraction_quality))
    weekly_manifest_data = read_json(WEEKLY_MANIFEST_FILE)
    prompt = build_user_prompt(selected_items, source_status_data, extraction_quality_data, weekly_manifest_data)

    if dry_run:
        audit = build_audit(
            enabled=True,
            status="dry_run",
            reason="Dry run requested; OpenAI API was not called.",
            model=selected_model,
            input_records=len(selected_items),
            summary_generated=False,
            validation_status="skipped",
            strict_source=strict_source,
        )
        print("[dry-run] 不会调用 OpenAI API。")
        print("LLM 摘要状态：dry_run")
        return 0, audit

    try:
        raw_output = call_openai(selected_model, str(api_key), prompt)
    except ImportError:
        audit = build_audit(
            enabled=True,
            status="sdk_missing",
            reason="OpenAI Python SDK is not installed.",
            model=selected_model,
            input_records=len(selected_items),
            summary_generated=False,
            validation_status="skipped",
            strict_source=strict_source,
            errors=["OpenAI Python SDK 缺失，请安装 requirements.txt。"],
        )
        write_json(audit_path, audit, dry_run)
        print("LLM 摘要状态：sdk_missing")
        return 2, audit
    except Exception as exc:
        audit = build_audit(
            enabled=True,
            status="api_error",
            reason="OpenAI API call failed.",
            model=selected_model,
            input_records=len(selected_items),
            summary_generated=False,
            validation_status="not_validated",
            strict_source=strict_source,
            errors=[exc.__class__.__name__],
        )
        write_json(audit_path, audit, dry_run)
        print("LLM 摘要状态：api_error")
        return (1 if fail_on_llm_error else 0), audit

    valid, summary, errors, warnings = validate_llm_output(raw_output, selected_items)
    if not valid or summary is None:
        audit = build_audit(
            enabled=True,
            status="validation_failed",
            reason="LLM output failed source-guardrail validation.",
            model=selected_model,
            input_records=len(selected_items),
            summary_generated=False,
            validation_status="failed",
            strict_source=strict_source,
            errors=errors,
            warnings=warnings,
        )
        write_json(audit_path, audit, dry_run)
        print("LLM 摘要状态：validation_failed")
        return (1 if fail_on_llm_error else 0), audit

    payload = {
        "generated_at": now_iso(),
        "llm_enabled": True,
        "llm_status": "generated",
        "model": selected_model,
        "input_records": len(selected_items),
        "summary": summary,
    }
    audit = build_audit(
        enabled=True,
        status="generated",
        reason="LLM summary generated and validated.",
        model=selected_model,
        input_records=len(selected_items),
        summary_generated=True,
        validation_status="passed",
        strict_source=strict_source,
        warnings=warnings,
    )
    write_json(output_path, payload, dry_run)
    write_json(audit_path, audit, dry_run)
    print("LLM 摘要状态：generated")
    return 0, audit


def main() -> int:
    parser = argparse.ArgumentParser(description="生成受来源约束的可选 LLM 摘要。")
    parser.add_argument("--enabled", action="store_true", help="显式启用 LLM 摘要。")
    parser.add_argument("--dry-run", action="store_true", help="演练流程，不写文件、不调用 OpenAI API。")
    parser.add_argument("--input-items", default="data/items.jsonl")
    parser.add_argument("--source-status", default="data/source_status.json")
    parser.add_argument("--extraction-quality", default="data/extraction_quality.json")
    parser.add_argument("--output", default="data/llm_summaries.json")
    parser.add_argument("--audit-output", default="data/llm_audit.json")
    parser.add_argument("--max-items", type=int, default=10)
    parser.add_argument("--model", default=None)
    parser.add_argument("--strict-source", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--fail-on-llm-error", action="store_true")
    args = parser.parse_args()

    if args.max_items < 1:
        print("--max-items 必须是大于等于 1 的整数。")
        return 2

    return_code, _audit = run_llm_summary(
        enabled=args.enabled,
        dry_run=args.dry_run,
        input_items=args.input_items,
        source_status=args.source_status,
        extraction_quality=args.extraction_quality,
        output=args.output,
        audit_output=args.audit_output,
        max_items=args.max_items,
        model=args.model,
        strict_source=args.strict_source,
        fail_on_llm_error=args.fail_on_llm_error,
    )
    return return_code


if __name__ == "__main__":
    sys.exit(main())
