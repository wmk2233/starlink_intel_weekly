from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from run_weekly import (  # noqa: E402
    apply_llm_to_meta,
    get_run_metadata,
    render_detail_failure_overview,
    render_llm_summary_section,
    render_structured_official_items,
)
from send_email import build_message  # noqa: E402


def report(baseline: int = 0) -> dict[str, object]:
    return {
        "sources": {
            "fixture": {
                "source_name": "Fixture Official",
                "baseline_items": baseline,
                "new_items": 0,
                "changed_items": 0,
                "unchanged_items": 1,
                "static_candidate_count": 0,
                "rendered_candidate_count": 1,
                "candidate_count_total": 1,
                "static_detail_success": 0,
                "rendered_detail_success": 0,
                "final_detail_success": 0,
                "final_detail_failed": 1,
                "final_success_rate": 0.0,
                "item_level_items": 0,
                "page_level_items": 1,
                "dominant_extracted_level": "page_level",
                "dominant_source_quality": "low",
                "failure_types": {"render_timeout": 1},
            }
        }
    }


class DynamicReportWordingTests(unittest.TestCase):
    def test_zero_baseline_omits_first_build_wording(self) -> None:
        text = render_structured_official_items([], report(0))
        self.assertNotIn("本次为条目级解析器首次成功运行", text)

    def test_positive_baseline_shows_explanation(self) -> None:
        text = render_structured_official_items([], report(1))
        self.assertIn("baseline 仅表示建立采集基线", text)

    def test_llm_enabled_wording(self) -> None:
        meta = get_run_metadata(False, True, "dual")
        apply_llm_to_meta(meta, {"llm_enabled": True, "llm_status": "generated", "guardrails": {}, "usage": {}})
        self.assertIn("当前自动化运行已显式启用 LLM", meta["llm_current_status_text"])

    def test_llm_disabled_wording(self) -> None:
        meta = get_run_metadata(False, True, "dual")
        apply_llm_to_meta(meta, {"llm_enabled": False, "llm_status": "skipped", "guardrails": {}, "usage": {}})
        self.assertIn("当前自动化运行未启用 LLM", meta["llm_current_status_text"])

    def test_missing_key_wording(self) -> None:
        meta = get_run_metadata(False, True, "dual")
        apply_llm_to_meta(meta, {"llm_enabled": True, "llm_status": "skipped_no_api_key", "guardrails": {}, "usage": {}})
        self.assertIn("未检测到对应 provider 的 API Key", meta["llm_current_status_text"])

    def test_final_core_input_is_displayed(self) -> None:
        meta = get_run_metadata(False, True, "dual")
        meta["llm_final_core_input_records"] = "2"
        self.assertIn("最终核心输入记录 | 2", render_llm_summary_section(meta, {}))

    def test_detail_failure_is_displayed(self) -> None:
        self.assertIn("render_timeout", render_detail_failure_overview(report()))

    def test_email_zero_baseline_omits_first_build_note(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            markdown = Path(directory) / "summary.md"
            markdown.write_text("fixture", encoding="utf-8")
            message = build_message(
                markdown,
                "2026-W01",
                {"MAIL_TO": "target@example.com", "MAIL_FROM": "sender@example.com"},
                {"baseline_items": "0"},
            )
        self.assertNotIn("本次为条目级解析首次建库", message.get_body().get_content())


if __name__ == "__main__":
    unittest.main()
