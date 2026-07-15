from __future__ import annotations

import unittest

from scripts.item_lifecycle import build_lifecycle_update_plan
from tests.lifecycle_helpers import complete_observation, item
from tests.phase4d_helpers import evaluate


class StaleRunProtectionTests(unittest.TestCase):
    def test_lifecycle_old_run_is_ignored(self) -> None:
        record = item(url="https://example.invalid/updates/item-a")
        newest = build_lifecycle_update_plan([record], [record], complete_observation(), run_id="new", observed_at="2026-02-10T00:00:00+00:00")
        stale = build_lifecycle_update_plan(newest.updated_items, newest.updated_items, complete_observation(), lifecycle_state=newest.updated_lifecycle_state, existing_versions=newest.all_versions, existing_events=newest.all_lifecycle_events, run_id="old", observed_at="2026-02-01T00:00:00+00:00")
        self.assertTrue(stale.ignored_as_stale)
        self.assertEqual(newest.updated_lifecycle_state, stale.updated_lifecycle_state)

    def test_alert_old_run_is_not_writable(self) -> None:
        newest = evaluate(run_id="new", started_at="2026-02-10T00:00:00+00:00")
        stale = evaluate(run_id="old", started_at="2026-02-01T00:00:00+00:00", previous_alert_state=newest.state, alert_events=newest.all_events)
        self.assertFalse(stale.write_allowed)
        self.assertTrue(stale.report["stale_run_ignored"])


if __name__ == "__main__":
    unittest.main()
