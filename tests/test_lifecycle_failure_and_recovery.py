from __future__ import annotations

import unittest

from scripts.item_lifecycle import build_lifecycle_update_plan
from tests.lifecycle_helpers import clone, complete_observation, item


class LifecycleFailureAndRecoveryTests(unittest.TestCase):
    def test_consecutive_failure_attention_and_recovery(self) -> None:
        old = item()
        plan = build_lifecycle_update_plan([old], [old], complete_observation(), run_id="failure-init")
        for attempt in range(1, 4):
            failed = clone(plan.updated_items[0])
            failed["seen_in_current_index"] = True
            failed["current_run_data_reused"] = True
            failed["detail_fetch_status"] = "failed_this_run"
            failed["last_detail_error_type"] = "request_timeout"
            plan = build_lifecycle_update_plan(
                plan.updated_items,
                [failed],
                complete_observation(),
                lifecycle_state=plan.updated_lifecycle_state,
                existing_versions=plan.all_versions,
                existing_events=plan.all_lifecycle_events,
                run_id=f"failure-{attempt}",
                detail_failure_attention_threshold=3,
            )
        state = plan.updated_lifecycle_state["items"]["record-1"]
        self.assertEqual("fetch_failed", state["lifecycle_state"])
        self.assertEqual(3, state["consecutive_detail_failures"])
        self.assertTrue(state["attention_required"])
        self.assertEqual("Existing official summary.", plan.updated_items[0]["summary"])

        recovered_item = clone(plan.updated_items[0])
        recovered_item["current_run_data_reused"] = False
        recovered_item["detail_fetch_status"] = "success"
        recovered_item["last_detail_error_type"] = None
        recovered = build_lifecycle_update_plan(
            plan.updated_items,
            [recovered_item],
            complete_observation(),
            lifecycle_state=plan.updated_lifecycle_state,
            existing_versions=plan.all_versions,
            existing_events=plan.all_lifecycle_events,
            run_id="recovery",
        )
        self.assertEqual("active", recovered.updated_items[0]["lifecycle_state"])
        self.assertEqual(0, recovered.updated_items[0]["consecutive_detail_failures"])
        self.assertIn("detail_fetch_recovered", recovered.updated_items[0]["lifecycle_events_this_run"])
        self.assertNotIn("service", recovered.lifecycle_report["events_this_run"][0]["reason"])


if __name__ == "__main__":
    unittest.main()
