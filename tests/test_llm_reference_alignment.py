from __future__ import annotations

import json
import unittest

from scripts.llm_summarize import (
    SUMMARY_VERSION,
    align_llm_references,
    build_user_prompt,
    validate_llm_output,
)


def allowed_records() -> list[dict[str, object]]:
    return [
        {
            "id": f"record-{index}",
            "source_id": "official",
            "record_scope": "item",
            "extracted_level": "item_level",
            "source_quality": "medium",
            "change_status": "unchanged",
            "title": f"Fixture {index}",
            "url": f"https://example.com/items/{index}",
            "canonical_url": f"https://example.com/items/{index}",
        }
        for index in range(1, 5)
    ]


def output(ids: list[str], urls: list[str]) -> dict[str, object]:
    return {
        "overall_summary": "本周未检测到新增或内容变化条目。",
        "key_points": [
            {
                "point": "本周未检测到新增或内容变化条目。",
                "source_record_ids": ids,
                "source_urls": urls,
                "caveat": "仅用于虚构夹具测试。",
            }
        ],
    }


class LlmReferenceAlignmentTests(unittest.TestCase):
    def test_extra_index_url_is_removed(self) -> None:
        records = allowed_records()
        ids = [str(record["id"]) for record in records]
        urls = [str(record["url"]) for record in records] + ["https://example.com/index"]
        aligned, stats = align_llm_references(output(ids, urls), records)
        self.assertEqual(1, stats["invalid_urls_removed"])
        self.assertEqual(4, len(aligned["key_points"][0]["source_urls"]))

    def test_valid_record_id_repairs_missing_url(self) -> None:
        aligned, stats = align_llm_references(output(["record-1"], []), allowed_records())
        self.assertEqual(["https://example.com/items/1"], aligned["key_points"][0]["source_urls"])
        self.assertEqual(1, stats["missing_urls_repaired"])

    def test_valid_url_repairs_missing_record_id(self) -> None:
        aligned, stats = align_llm_references(
            output([], ["https://example.com/items/2"]),
            allowed_records(),
        )
        self.assertEqual(["record-2"], aligned["key_points"][0]["source_record_ids"])
        self.assertEqual(1, stats["missing_record_ids_repaired"])

    def test_mismatched_valid_pair_is_not_forced(self) -> None:
        aligned, stats = align_llm_references(
            output(["record-1"], ["https://example.com/items/2"]),
            allowed_records(),
        )
        self.assertEqual([], aligned["key_points"])
        self.assertEqual(1, stats["mismatched_reference_pairs_removed"])
        self.assertEqual("failed", stats["reference_alignment_status"])

    def test_unknown_url_is_removed(self) -> None:
        aligned, stats = align_llm_references(
            output([], ["https://unknown.example/item"]),
            allowed_records(),
        )
        self.assertEqual([], aligned["key_points"])
        self.assertEqual(1, stats["invalid_urls_removed"])

    def test_unknown_record_id_is_removed(self) -> None:
        aligned, stats = align_llm_references(output(["unknown"], []), allowed_records())
        self.assertEqual([], aligned["key_points"])
        self.assertEqual(1, stats["invalid_record_ids_removed"])

    def test_key_point_without_sources_is_removed(self) -> None:
        aligned, stats = align_llm_references(output([], []), allowed_records())
        self.assertEqual([], aligned["key_points"])
        self.assertEqual(1, stats["key_points_removed_without_sources"])

    def test_monitoring_url_is_not_core_input_or_reference(self) -> None:
        monitoring_url = "https://example.com/monitoring-index"
        prompt = build_user_prompt(
            allowed_records(),
            source_status={"sources": {"official": {"url": monitoring_url}}},
            monitoring_context=[{"source_url": monitoring_url}],
        )
        self.assertNotIn(monitoring_url, prompt)
        self.assertNotIn("monitoring_context", json.loads(prompt))
        aligned, stats = align_llm_references(output([], [monitoring_url]), allowed_records())
        self.assertEqual([], aligned["key_points"])
        self.assertEqual(1, stats["invalid_urls_removed"])

    def test_source_based_notes_are_removed_from_model_output(self) -> None:
        raw = output(["record-1"], ["https://example.com/items/1"])
        raw["source_based_notes"] = [{"source_urls": ["https://example.com/index"]}]
        aligned, stats = align_llm_references(raw, allowed_records())
        self.assertNotIn("source_based_notes", aligned)
        self.assertEqual(1, stats["source_based_notes_removed"])
        self.assertNotIn("source_based_notes", json.loads(build_user_prompt(allowed_records()))["instructions"]["output_json_schema"])

    def test_aligned_output_passes_strict_validation(self) -> None:
        raw = output(["record-1"], [])
        aligned, _stats = align_llm_references(raw, allowed_records())
        valid, _summary, errors, _warnings = validate_llm_output(
            json.dumps(aligned),
            allowed_records(),
        )
        self.assertTrue(valid, errors)
        self.assertEqual(SUMMARY_VERSION, aligned["llm_summary_version"])

    def test_unrepairable_output_still_fails_validation(self) -> None:
        raw = output(["record-1"], ["https://example.com/items/2"])
        aligned, _stats = align_llm_references(raw, allowed_records())
        valid, _summary, errors, _warnings = validate_llm_output(
            json.dumps(aligned),
            allowed_records(),
        )
        self.assertFalse(valid)
        self.assertTrue(any("没有可验证" in error for error in errors))

    def test_claim_text_is_not_modified(self) -> None:
        raw = output(["record-1"], [])
        claim = raw["key_points"][0]["point"]
        aligned, _stats = align_llm_references(raw, allowed_records())
        self.assertEqual(claim, aligned["key_points"][0]["point"])


if __name__ == "__main__":
    unittest.main()
