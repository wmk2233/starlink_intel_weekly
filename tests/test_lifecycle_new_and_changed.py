from __future__ import annotations

import unittest

from scripts.item_lifecycle import build_lifecycle_update_plan, compare_semantic_versions
from tests.lifecycle_helpers import clone, complete_observation, item


class LifecycleNewAndChangedTests(unittest.TestCase):
    def test_new_item_is_first_observed_and_idempotent(self) -> None:
        current = item()
        first = build_lifecycle_update_plan([], [current], complete_observation(), run_id="new-1")
        self.assertEqual("new", first.updated_items[0]["change_status"])
        self.assertEqual("item_discovered", first.lifecycle_report["events_this_run"][0]["event_type"])
        self.assertEqual("new_item", first.new_versions[0]["version_kind"])

        next_item = clone(first.updated_items[0])
        next_item["seen_in_current_index"] = True
        second = build_lifecycle_update_plan(
            first.updated_items,
            [next_item],
            complete_observation(),
            lifecycle_state=first.updated_lifecycle_state,
            existing_versions=first.all_versions,
            existing_events=first.all_lifecycle_events,
            run_id="new-2",
        )
        self.assertEqual("unchanged", second.updated_items[0]["change_status"])
        self.assertEqual(0, second.lifecycle_report["totals"]["new"])

    def test_semantic_change_increments_version_and_keeps_evidence(self) -> None:
        old = item()
        initial = build_lifecycle_update_plan([old], [old], complete_observation(), run_id="init")
        changed = clone(initial.updated_items[0])
        changed["title"] = "Updated official title"
        changed["structured_fields"] = {"status": "updated"}
        changed["seen_in_current_index"] = True
        plan = build_lifecycle_update_plan(
            initial.updated_items,
            [changed],
            complete_observation(),
            lifecycle_state=initial.updated_lifecycle_state,
            existing_versions=initial.all_versions,
            existing_events=initial.all_lifecycle_events,
            run_id="change-1",
        )
        self.assertEqual("changed", plan.updated_items[0]["change_status"])
        self.assertEqual(2, plan.updated_items[0]["semantic_version"])
        event = next(value for value in plan.new_lifecycle_events if value["event_type"] == "semantic_content_changed")
        self.assertIn("title", event["changed_fields"])
        self.assertIn("before_excerpt", event["change_evidence"]["title"])

    def test_whitespace_and_entities_do_not_change_semantics(self) -> None:
        old = item(title="A & B", evidence="A factual sentence.")
        current = clone(old)
        current["title"] = "  A &amp; B  "
        current["evidence"] = "A   factual\n sentence."
        comparison = compare_semantic_versions(old, current)
        self.assertFalse(comparison["semantic_changed"])


if __name__ == "__main__":
    unittest.main()
