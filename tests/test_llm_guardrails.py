from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from scripts.llm_summarize import (
    SUMMARY_VERSION,
    build_monitoring_context,
    extract_response_usage,
    run_llm_summary,
    validate_llm_output,
)


def source_record() -> dict[str, object]:
    return {
        "id": "record-1",
        "source_id": "official",
        "source_name": "Official Source",
        "url": "https://example.com/source",
        "change_status": "unchanged",
        "extracted_level": "page_level",
        "source_quality": "low",
        "last_seen_at": "2026-07-14T00:00:00+00:00",
    }


def valid_summary() -> dict[str, object]:
    return {
        "llm_summary_version": SUMMARY_VERSION,
        "overall_summary": "本周未检测到新增或内容变化条目。",
        "key_points": [
            {
                "point": "本周未检测到新增或内容变化条目。",
                "source_record_ids": ["record-1"],
                "source_urls": ["https://example.com/source"],
                "caveat": "页面级记录。",
            }
        ],
    }


class LlmGuardrailTests(unittest.TestCase):
    def test_unknown_record_id_is_rejected(self) -> None:
        summary = valid_summary()
        summary["key_points"][0]["source_record_ids"] = ["unknown"]  # type: ignore[index]
        valid, _summary, errors, _warnings = validate_llm_output(json.dumps(summary), [source_record()])
        self.assertFalse(valid)
        self.assertTrue(any("输入外 record id" in error for error in errors))

    def test_unknown_url_is_rejected(self) -> None:
        summary = valid_summary()
        summary["key_points"][0]["source_urls"] = ["https://unknown.example/source"]  # type: ignore[index]
        valid, _summary, errors, _warnings = validate_llm_output(json.dumps(summary), [source_record()])
        self.assertFalse(valid)
        self.assertTrue(any("输入外 URL" in error for error in errors))

    def test_key_point_without_source_is_rejected(self) -> None:
        summary = valid_summary()
        summary["key_points"][0]["source_record_ids"] = []  # type: ignore[index]
        valid, _summary, errors, _warnings = validate_llm_output(json.dumps(summary), [source_record()])
        self.assertFalse(valid)
        self.assertTrue(any("缺少来源记录" in error for error in errors))

    def test_page_level_launch_success_is_rejected(self) -> None:
        summary = valid_summary()
        summary["overall_summary"] = "本周未检测到新增或内容变化条目，但发射成功。"
        valid, _summary, errors, _warnings = validate_llm_output(json.dumps(summary), [source_record()])
        self.assertFalse(valid)
        self.assertTrue(any("发射成功" in error for error in errors))

    def test_page_level_technical_upgrade_is_rejected(self) -> None:
        summary = valid_summary()
        summary["overall_summary"] = "本周未检测到新增或内容变化条目，但技术升级。"
        valid, _summary, errors, _warnings = validate_llm_output(json.dumps(summary), [source_record()])
        self.assertFalse(valid)
        self.assertTrue(any("技术升级" in error for error in errors))

    def test_page_changed_without_item_changes_has_deterministic_explanation(self) -> None:
        status = {
            "sources": {
                "official": {
                    "source_name": "Official Source",
                    "change_status": "changed",
                    "new_items": 0,
                    "changed_items": 0,
                }
            }
        }
        context = build_monitoring_context(status, {"sources": {}}, [source_record()])
        self.assertEqual(
            "页面级 hash 发生变化，但当前规则未检测到可确认的新增或内容变化条目。",
            context[0]["interpretation"],
        )

    def _run_with_mock_output(self, raw_output: str, directory: str) -> tuple[int, dict[str, object], Path]:
        root = Path(directory)
        items = root / "items.jsonl"
        status = root / "source_status.json"
        quality = root / "extraction_quality.json"
        output = root / "summary.json"
        audit = root / "audit.json"
        usage = root / "usage.jsonl"
        items.write_text(json.dumps(source_record()) + "\n", encoding="utf-8")
        status.write_text(json.dumps({"sources": {"official": {"change_status": "unchanged", "new_items": 0, "changed_items": 0}}}), encoding="utf-8")
        quality.write_text(json.dumps({"sources": {}}), encoding="utf-8")
        output.write_text('{"sentinel": true}\n', encoding="utf-8")
        with patch.dict("os.environ", {"DEEPSEEK_API_KEY": "unit-test-placeholder-key"}, clear=False):
            with patch("scripts.llm_summarize.call_deepseek", return_value=(raw_output, extract_response_usage(SimpleNamespace(usage=None)))):
                code, audit_data = run_llm_summary(
                    enabled=True,
                    dry_run=False,
                    input_items=items,
                    source_status=status,
                    extraction_quality=quality,
                    output=output,
                    audit_output=audit,
                    usage_output=usage,
                    provider="deepseek",
                )
        return code, audit_data, output

    def test_validation_failure_does_not_overwrite_summary(self) -> None:
        summary = valid_summary()
        summary["key_points"][0]["source_record_ids"] = ["unknown"]  # type: ignore[index]
        summary["key_points"][0]["source_urls"] = ["https://unknown.example/source"]  # type: ignore[index]
        with tempfile.TemporaryDirectory() as directory:
            _code, audit, output = self._run_with_mock_output(json.dumps(summary), directory)
            self.assertEqual("validation_failed", audit["llm_status"])
            self.assertEqual({"sentinel": True}, json.loads(output.read_text(encoding="utf-8")))

    def test_invalid_json_does_not_overwrite_summary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _code, audit, output = self._run_with_mock_output("not-json", directory)
            self.assertEqual("validation_failed", audit["llm_status"])
            self.assertEqual({"sentinel": True}, json.loads(output.read_text(encoding="utf-8")))

    def test_valid_output_is_generated_with_allowed_pairs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _code, audit, output = self._run_with_mock_output(json.dumps(valid_summary()), directory)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual("generated", audit["llm_status"])
            self.assertEqual(
                [{"record_id": "record-1", "canonical_url": "https://example.com/source"}],
                payload["allowed_reference_pairs"],
            )
            self.assertNotIn("source_based_notes", payload["summary"])

    def test_source_based_notes_are_rejected_by_strict_validation(self) -> None:
        summary = valid_summary()
        summary["source_based_notes"] = []
        valid, _summary, errors, _warnings = validate_llm_output(json.dumps(summary), [source_record()])
        self.assertFalse(valid)
        self.assertTrue(any("不得由模型生成" in error for error in errors))

    def test_dry_run_does_not_write_usage(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            usage = Path(directory) / "usage.jsonl"
            run_llm_summary(enabled=True, dry_run=True, usage_output=usage, provider="deepseek")
            self.assertFalse(usage.exists())

    def test_usage_tokens_can_be_null(self) -> None:
        usage = extract_response_usage(SimpleNamespace(usage=None))
        self.assertIsNone(usage["prompt_tokens"])
        self.assertIsNone(usage["completion_tokens"])
        self.assertIsNone(usage["total_tokens"])


if __name__ == "__main__":
    unittest.main()
