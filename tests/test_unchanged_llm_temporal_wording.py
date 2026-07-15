from __future__ import annotations

import json
import unittest

from scripts.llm_summarize import SUMMARY_VERSION, system_prompt, validate_llm_output


def record(status: str, *, published_at=None) -> dict:
    return {
        "id": "record-1",
        "source_id": "fixture_official",
        "record_scope": "item",
        "extracted_level": "item_level",
        "source_quality": "medium",
        "change_status": status,
        "title": "Synthetic official fixture",
        "url": "https://example.invalid/items/1",
        "canonical_url": "https://example.invalid/items/1",
        "published_at": published_at,
    }


def output(point: str, overall: str) -> str:
    return json.dumps(
        {
            "llm_summary_version": SUMMARY_VERSION,
            "overall_summary": overall,
            "key_points": [
                {
                    "point": point,
                    "source_record_ids": ["record-1"],
                    "source_urls": ["https://example.invalid/items/1"],
                    "caveat": "Synthetic fixture only.",
                }
            ],
        }
    )


class UnchangedLlmTemporalWordingTests(unittest.TestCase):
    def test_prompt_contains_explicit_unchanged_time_guardrail(self) -> None:
        prompt = system_prompt()
        self.assertIn("change_status=unchanged", prompt)
        self.assertIn("现有官方条目介绍", prompt)
        self.assertIn("新近上线", prompt)

    def test_unchanged_current_week_wording_fails(self) -> None:
        valid, _summary, errors, _warnings = validate_llm_output(
            output("该条目本周发布相关说明。", "本周未检测到新增或内容变化条目。"),
            [record("unchanged")],
        )
        self.assertFalse(valid)
        self.assertTrue(any("unchanged" in error or "本周时点" in error for error in errors))

    def test_unchanged_historical_wording_passes(self) -> None:
        valid, _summary, errors, _warnings = validate_llm_output(
            output("已有官方记录显示该历史条目包含相关说明。", "本周未检测到新增或内容变化条目。"),
            [record("unchanged")],
        )
        self.assertTrue(valid, errors)

    def test_changed_is_not_automatic_weekly_release(self) -> None:
        valid, _summary, errors, _warnings = validate_llm_output(
            output("官方本周发布该条目。", "本轮检测到内容变化。"),
            [record("changed")],
        )
        self.assertFalse(valid)
        self.assertTrue(any("changed" in error for error in errors))

    def test_new_requires_date_for_weekly_release_wording(self) -> None:
        invalid, _summary, errors, _warnings = validate_llm_output(
            output("官方本周发布该条目。", "本轮首次发现该条目。"),
            [record("new")],
        )
        valid, _summary, valid_errors, _warnings = validate_llm_output(
            output("官方本周发布该条目。", "本轮首次发现且输入包含明确日期证据。"),
            [record("new", published_at="2026-01-01")],
        )
        self.assertFalse(invalid)
        self.assertTrue(any("日期证据" in error for error in errors))
        self.assertTrue(valid, valid_errors)


if __name__ == "__main__":
    unittest.main()
