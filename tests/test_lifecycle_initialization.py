from __future__ import annotations

import unittest

from scripts.item_lifecycle import build_lifecycle_update_plan
from tests.lifecycle_helpers import complete_observation, item, page_record


class LifecycleInitializationTests(unittest.TestCase):
    def test_existing_items_initialize_once_without_new_or_changed(self) -> None:
        existing = [item(f"record-{index}", f"https://starlink.com/updates/{index}") for index in range(5)]
        plan = build_lifecycle_update_plan(
            existing,
            existing,
            complete_observation(),
            run_id="migration-1",
            observed_at="2026-06-01T00:00:00+00:00",
        )
        self.assertEqual(5, plan.lifecycle_report["totals"]["initialized"])
        self.assertEqual(0, plan.lifecycle_report["totals"]["new"])
        self.assertEqual(0, plan.lifecycle_report["totals"]["changed"])
        self.assertEqual(5, len(plan.new_versions))
        self.assertEqual(5, plan.lifecycle_report["totals"]["new_semantic_versions"])
        self.assertEqual(5, plan.lifecycle_report["totals"]["new_extraction_revisions"])
        self.assertTrue(all(value["lifecycle_state"] == "active" for value in plan.updated_lifecycle_state["items"].values()))
        self.assertTrue(all(value["change_status"] == "unchanged" for value in plan.updated_items))

        second = build_lifecycle_update_plan(
            plan.updated_items,
            plan.updated_items,
            complete_observation(),
            lifecycle_state=plan.updated_lifecycle_state,
            existing_versions=plan.all_versions,
            existing_events=plan.all_lifecycle_events,
            run_id="migration-2",
            observed_at="2026-06-08T00:00:00+00:00",
        )
        self.assertEqual(0, second.lifecycle_report["totals"]["initialized"])
        self.assertEqual(5, len(second.all_versions))

    def test_page_level_record_is_not_migrated(self) -> None:
        existing = [item(), page_record()]
        plan = build_lifecycle_update_plan(existing, existing, complete_observation(), run_id="page-skip")
        self.assertEqual({"record-1"}, set(plan.updated_lifecycle_state["items"]))


if __name__ == "__main__":
    unittest.main()
