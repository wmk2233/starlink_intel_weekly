from __future__ import annotations

import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from scripts.item_lifecycle import build_lifecycle_update_plan, write_lifecycle_transaction
from tests.lifecycle_helpers import complete_observation, item


class ItemVersionHistoryTests(unittest.TestCase):
    def test_extraction_improvement_does_not_increment_semantic_version(self) -> None:
        old = item()
        initial = build_lifecycle_update_plan([old], [old], complete_observation(), run_id="version-init")
        improved = deepcopy(initial.updated_items[0])
        improved["published_at"] = "2026-06-01T00:00:00+00:00"
        improved["field_evidence"]["published_at"] = "time element"
        improved["extraction_confidence"] = 0.9
        plan = build_lifecycle_update_plan(
            initial.updated_items,
            [improved],
            complete_observation(),
            lifecycle_state=initial.updated_lifecycle_state,
            existing_versions=initial.all_versions,
            existing_events=initial.all_lifecycle_events,
            run_id="version-improved",
        )
        self.assertEqual("unchanged", plan.updated_items[0]["change_status"])
        self.assertEqual("improved", plan.updated_items[0]["extraction_change_status"])
        self.assertEqual(1, plan.updated_items[0]["semantic_version"])
        self.assertEqual(2, plan.updated_items[0]["extraction_revision"])
        self.assertEqual("extraction_improvement", plan.new_versions[0]["version_kind"])

    def test_versions_are_deduplicated_bounded_and_transactional(self) -> None:
        old = item()
        plan = build_lifecycle_update_plan([old], [old], complete_observation(), run_id="transaction-init")
        duplicate = deepcopy(plan.all_versions[0])
        bounded = build_lifecycle_update_plan(
            plan.updated_items,
            plan.updated_items,
            complete_observation(),
            lifecycle_state=plan.updated_lifecycle_state,
            existing_versions=[duplicate, duplicate],
            existing_events=plan.all_lifecycle_events,
            run_id="transaction-next",
            max_item_versions_per_record=1,
        )
        self.assertEqual(1, len(bounded.all_versions))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_lifecycle_transaction(
                bounded,
                items_path=root / "items.jsonl",
                lifecycle_state_path=root / "state.json",
                versions_path=root / "versions.jsonl",
                events_path=root / "events.jsonl",
                report_path=root / "report.json",
            )
            self.assertEqual("4C", json.loads((root / "report.json").read_text(encoding="utf-8"))["stage"])
            self.assertNotIn("<html", (root / "versions.jsonl").read_text(encoding="utf-8").lower())


if __name__ == "__main__":
    unittest.main()
