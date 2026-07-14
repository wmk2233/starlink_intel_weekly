from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from scripts.llm_summarize import (
    deduplicate_llm_input_records,
    normalize_and_deduplicate_llm_references,
    normalize_source_url,
)


class LlmDedupTests(unittest.TestCase):
    def setUp(self) -> None:
        self.records = [
            {
                "id": "old",
                "source_id": "official",
                "url": "https://example.com/news/?utm_source=test#top",
                "last_seen_at": "2026-07-01T00:00:00+00:00",
                "summary": "old",
            },
            {
                "id": "new",
                "source_id": "official",
                "url": "https://EXAMPLE.com/news",
                "last_seen_at": "2026-07-02T00:00:00+00:00",
                "summary": "new",
            },
        ]

    def test_same_source_and_url_keeps_one_record(self) -> None:
        records, stats = deduplicate_llm_input_records(self.records)
        self.assertEqual(1, len(records))
        self.assertEqual(1, stats["duplicate_records_removed"])

    def test_latest_last_seen_record_is_selected(self) -> None:
        records, _stats = deduplicate_llm_input_records(self.records)
        self.assertEqual("new", records[0]["id"])

    def test_trailing_slash_is_normalized(self) -> None:
        self.assertEqual("https://example.com/news", normalize_source_url("https://example.com/news/"))

    def test_fragment_is_removed(self) -> None:
        self.assertEqual("https://example.com/news", normalize_source_url("https://example.com/news#part"))

    def test_tracking_query_is_removed(self) -> None:
        self.assertEqual("https://example.com/news", normalize_source_url("https://example.com/news?utm_campaign=x"))

    def test_business_query_is_preserved(self) -> None:
        records = [
            {"source_id": "official", "url": "https://example.com/news?id=1"},
            {"source_id": "official", "url": "https://example.com/news?id=2"},
        ]
        deduplicated, _stats = deduplicate_llm_input_records(records)
        self.assertEqual(2, len(deduplicated))

    def test_output_url_references_are_deduplicated(self) -> None:
        output = {
            "key_points": [{"source_record_ids": ["new"], "source_urls": ["https://example.com/news/", "https://example.com/news#x"]}],
            "source_based_notes": [],
        }
        normalized, stats = normalize_and_deduplicate_llm_references(output, [self.records[1]])
        self.assertEqual(["https://example.com/news"], normalized["key_points"][0]["source_urls"])
        self.assertEqual(2, stats["output_url_references_before_dedup"])
        self.assertEqual(1, stats["output_url_references_after_dedup"])

    def test_output_reference_order_is_stable(self) -> None:
        output = {
            "key_points": [{"source_record_ids": ["b", "a", "b"], "source_urls": ["https://b.example/x", "https://a.example/x", "https://b.example/x/"]}],
            "source_based_notes": [],
        }
        allowed = [
            {"id": "a", "url": "https://a.example/x"},
            {"id": "b", "url": "https://b.example/x"},
        ]
        normalized, _stats = normalize_and_deduplicate_llm_references(output, allowed)
        self.assertEqual(["b", "a"], normalized["key_points"][0]["source_record_ids"])
        self.assertEqual(["https://b.example/x", "https://a.example/x"], normalized["key_points"][0]["source_urls"])

    def test_original_input_is_not_mutated(self) -> None:
        original = copy.deepcopy(self.records)
        deduplicate_llm_input_records(self.records)
        self.assertEqual(original, self.records)

    def test_items_history_file_is_not_modified(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "items.jsonl"
            path.write_text("".join(json.dumps(record) + "\n" for record in self.records), encoding="utf-8")
            before = path.read_bytes()
            deduplicate_llm_input_records(self.records)
            self.assertEqual(before, path.read_bytes())


if __name__ == "__main__":
    unittest.main()
