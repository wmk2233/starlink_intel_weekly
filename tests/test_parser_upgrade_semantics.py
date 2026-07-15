from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from collect_sources import apply_official_item_baseline_metadata  # noqa: E402
from parsers.common import semantic_content_hash  # noqa: E402


def item(parser: str = "starlink_updates_item_v1") -> dict[str, object]:
    record = {
        "id": "fixture-id",
        "source_id": "starlink_official_updates",
        "record_scope": "item",
        "canonical_url": "https://starlink.com/updates/fixture",
        "url": "https://starlink.com/updates/fixture",
        "title": "Fixture title",
        "published_at": None,
        "published_date_text": None,
        "summary": "Fixture summary",
        "evidence": "Fictional source evidence used to test semantic hashing without any real claim.",
        "structured_fields": {},
        "starlink_relevance": "direct",
        "field_evidence": {"title": "static_h1", "evidence": "static_article"},
        "parser_version": parser,
        "fetched_at": "2026-01-02T00:00:00+00:00",
        "extraction_hash": "extract-v1" if parser.endswith("v1") else "extract-v2",
    }
    record["semantic_content_hash"] = semantic_content_hash(record)
    record["content_hash"] = record["semantic_content_hash"]
    return record


def classify(old: dict[str, object], new: dict[str, object]) -> dict[str, object]:
    state = {"bootstrap_completed": True, "items": {}}
    apply_official_item_baseline_metadata([new], {"fixture-id": old}, state, True)
    return new


class ParserUpgradeSemanticsTests(unittest.TestCase):
    def test_v1_to_v2_is_not_automatic_changed(self) -> None:
        updated = classify(item("starlink_updates_item_v1"), item("starlink_updates_item_v2"))
        self.assertEqual(updated["change_status"], "unchanged")

    def test_field_evidence_change_is_improved(self) -> None:
        old = item()
        new = item("starlink_updates_item_v2")
        new["field_evidence"] = {"title": "rendered_h1", "evidence": "rendered_article"}
        updated = classify(old, new)
        self.assertEqual(updated["extraction_change_status"], "improved")

    def test_added_date_during_upgrade_is_enrichment(self) -> None:
        old = item()
        new = item("starlink_updates_item_v2")
        new["published_at"] = "2026-01-01T00:00:00+00:00"
        new["semantic_content_hash"] = semantic_content_hash(new)
        updated = classify(old, new)
        self.assertEqual(updated["change_reason"], "parser_enrichment")

    def test_expanded_title_during_upgrade_is_enrichment(self) -> None:
        old = item()
        new = item("starlink_updates_item_v2")
        new["title"] = "Fixture title: Expanded official heading"
        new["semantic_content_hash"] = semantic_content_hash(new)
        updated = classify(old, new)
        self.assertEqual(updated["change_status"], "unchanged")
        self.assertEqual(updated["change_reason"], "parser_enrichment")

    def test_title_fact_change_is_changed(self) -> None:
        old = item("starlink_updates_item_v2")
        new = copy.deepcopy(old)
        new["title"] = "Different fixture title"
        new["semantic_content_hash"] = semantic_content_hash(new)
        updated = classify(old, new)
        self.assertEqual(updated["change_status"], "changed")

    def test_evidence_fact_change_is_changed(self) -> None:
        old = item("starlink_updates_item_v2")
        new = copy.deepcopy(old)
        new["evidence"] = "A materially different fictional evidence paragraph for semantic change testing."
        new["semantic_content_hash"] = semantic_content_hash(new)
        updated = classify(old, new)
        self.assertEqual(updated["change_status"], "changed")

    def test_parser_version_not_in_semantic_hash(self) -> None:
        self.assertEqual(semantic_content_hash(item("v1")), semantic_content_hash(item("v2")))

    def test_newly_recovered_item_during_parser_upgrade_is_not_new(self) -> None:
        recovered = item("starlink_updates_item_v2")
        state = {"bootstrap_completed": True, "items": {}}
        apply_official_item_baseline_metadata(
            [recovered],
            {},
            state,
            True,
            previous_parser_version="starlink_updates_item_v1",
        )
        self.assertEqual(recovered["change_status"], "unchanged")
        self.assertEqual(recovered["extraction_change_status"], "improved")
        self.assertEqual(recovered["change_reason"], "parser_enrichment_discovery")

    def test_quality_not_in_semantic_hash(self) -> None:
        first = item()
        second = copy.deepcopy(first)
        first["source_quality"] = "medium"
        second["source_quality"] = "high"
        self.assertEqual(semantic_content_hash(first), semantic_content_hash(second))

    def test_extraction_method_not_in_semantic_hash(self) -> None:
        first = item()
        second = copy.deepcopy(first)
        second["field_evidence"] = {"title": "rendered_h1", "evidence": "rendered_article"}
        self.assertEqual(semantic_content_hash(first), semantic_content_hash(second))


if __name__ == "__main__":
    unittest.main()
