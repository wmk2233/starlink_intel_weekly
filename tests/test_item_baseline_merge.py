from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from collect_sources import apply_official_item_baseline_metadata, load_items, write_items_upsert  # noqa: E402


def record(item_id: str = "item-a", content_hash: str = "hash-a") -> dict[str, object]:
    return {
        "id": item_id,
        "source_id": "spacex_official_launches",
        "record_scope": "item",
        "canonical_url": f"https://www.spacex.com/launches/{item_id}",
        "url": f"https://www.spacex.com/launches/{item_id}",
        "title": item_id,
        "evidence": "official evidence",
        "content_hash": content_hash,
        "fetched_at": "2026-07-14T00:00:00+00:00",
        "seen_in_current_index": True,
    }


class BaselineMergeTests(unittest.TestCase):
    def test_first_success_is_baseline(self) -> None:
        item = record()
        state: dict[str, object] = {"bootstrap_completed": False, "items": {}}
        counts = apply_official_item_baseline_metadata([item], {}, state, True)
        self.assertEqual(counts, (1, 0, 0, 0))

    def test_first_success_completes_bootstrap(self) -> None:
        state: dict[str, object] = {"bootstrap_completed": False, "items": {}}
        apply_official_item_baseline_metadata([record()], {}, state, True)
        self.assertTrue(state["bootstrap_completed"])

    def test_failure_does_not_complete_bootstrap(self) -> None:
        state: dict[str, object] = {"bootstrap_completed": False, "items": {}}
        apply_official_item_baseline_metadata([], {}, state, False)
        self.assertFalse(state["bootstrap_completed"])

    def test_new_url_after_bootstrap_is_new(self) -> None:
        item = record("item-b")
        state: dict[str, object] = {"bootstrap_completed": True, "items": {}}
        counts = apply_official_item_baseline_metadata([item], {}, state, True)
        self.assertEqual(counts, (0, 1, 0, 0))

    def test_hash_change_is_changed(self) -> None:
        old = record(content_hash="old")
        item = record(content_hash="new")
        state: dict[str, object] = {"bootstrap_completed": True, "items": {}}
        counts = apply_official_item_baseline_metadata([item], {"item-a": old}, state, True)
        self.assertEqual(counts, (0, 0, 1, 0))

    def test_same_hash_is_unchanged(self) -> None:
        old = record()
        item = record()
        state: dict[str, object] = {"bootstrap_completed": True, "items": {}}
        counts = apply_official_item_baseline_metadata([item], {"item-a": old}, state, True)
        self.assertEqual(counts, (0, 0, 0, 1))

    def test_rebootstrap_forces_baseline(self) -> None:
        old = record()
        item = record()
        state: dict[str, object] = {"bootstrap_completed": True, "items": {}}
        counts = apply_official_item_baseline_metadata([item], {"item-a": old}, state, True, rebootstrap=True)
        self.assertEqual(counts[0], 1)

    def test_page_record_is_not_baseline(self) -> None:
        item = record()
        item["record_scope"] = "page"
        state: dict[str, object] = {"bootstrap_completed": False, "items": {}}
        counts = apply_official_item_baseline_metadata([item], {}, state, False)
        self.assertEqual(counts, (0, 0, 0, 0))

    def test_upsert_keeps_missing_history(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "items.jsonl"
            old = record("old")
            old["change_status"] = "baseline"
            write_items_upsert([old], path, {"spacex_official_launches"})
            new = record("new")
            new["change_status"] = "new"
            write_items_upsert([new], path, {"spacex_official_launches"})
            self.assertEqual(len(load_items(path)), 2)

    def test_missing_history_is_marked_not_seen(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "items.jsonl"
            old = record("old")
            old["change_status"] = "baseline"
            write_items_upsert([old], path, {"spacex_official_launches"})
            new = record("new")
            new["change_status"] = "new"
            write_items_upsert([new], path, {"spacex_official_launches"})
            records = {item["id"]: item for item in load_items(path)}
            self.assertFalse(records["old"]["seen_in_current_index"])

    def test_parser_version_change_does_not_reset_bootstrap(self) -> None:
        old = record()
        item = record()
        item["parser_version"] = "new_parser_version"
        state: dict[str, object] = {"bootstrap_completed": True, "parser_version": "old_parser_version", "items": {}}
        counts = apply_official_item_baseline_metadata([item], {"item-a": old}, state, True)
        self.assertEqual(counts, (0, 0, 0, 1))


if __name__ == "__main__":
    unittest.main()
