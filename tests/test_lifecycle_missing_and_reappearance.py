from __future__ import annotations

import unittest

from scripts.item_lifecycle import build_lifecycle_update_plan
from tests.lifecycle_helpers import clone, complete_observation, item


class LifecycleMissingAndReappearanceTests(unittest.TestCase):
    def setUp(self) -> None:
        old = item()
        self.initial = build_lifecycle_update_plan(
            [old], [old], complete_observation(), run_id="missing-init", observed_at="2026-06-01T00:00:00+00:00"
        )

    def _missing(self, plan, run_id: str, observed_at: str, complete: bool = True):
        absent = clone(plan.updated_items[0])
        absent["seen_in_current_index"] = False
        return build_lifecycle_update_plan(
            plan.updated_items,
            [absent],
            complete_observation(complete),
            lifecycle_state=plan.updated_lifecycle_state,
            existing_versions=plan.all_versions,
            existing_events=plan.all_lifecycle_events,
            run_id=run_id,
            observed_at=observed_at,
            long_absence_observation_threshold=2,
            long_absence_min_days=14,
        )

    def test_index_failure_does_not_increment_missing(self) -> None:
        failed = self._missing(self.initial, "failed-index", "2026-06-02T00:00:00+00:00", complete=False)
        state = failed.updated_lifecycle_state["items"]["record-1"]
        self.assertEqual(0, state["consecutive_missing_observations"])
        self.assertEqual("active", state["lifecycle_state"])

    def test_missing_long_absence_and_reappearance(self) -> None:
        first = self._missing(self.initial, "missing-1", "2026-06-02T00:00:00+00:00")
        self.assertEqual("temporarily_missing", first.updated_items[0]["lifecycle_state"])
        too_early = self._missing(first, "missing-2", "2026-06-05T00:00:00+00:00")
        self.assertEqual("temporarily_missing", too_early.updated_items[0]["lifecycle_state"])
        long_absent = self._missing(too_early, "missing-3", "2026-06-17T00:00:00+00:00")
        self.assertEqual("long_absent", long_absent.updated_items[0]["lifecycle_state"])

        present = clone(long_absent.updated_items[0])
        present["seen_in_current_index"] = True
        reappeared = build_lifecycle_update_plan(
            long_absent.updated_items,
            [present],
            complete_observation(),
            lifecycle_state=long_absent.updated_lifecycle_state,
            existing_versions=long_absent.all_versions,
            existing_events=long_absent.all_lifecycle_events,
            run_id="reappeared",
            observed_at="2026-06-18T00:00:00+00:00",
        )
        self.assertEqual("active", reappeared.updated_items[0]["lifecycle_state"])
        self.assertEqual("unchanged", reappeared.updated_items[0]["change_status"])
        self.assertEqual(0, reappeared.updated_items[0]["consecutive_missing_observations"])
        self.assertIn("reappeared", reappeared.updated_items[0]["lifecycle_events_this_run"])


if __name__ == "__main__":
    unittest.main()
