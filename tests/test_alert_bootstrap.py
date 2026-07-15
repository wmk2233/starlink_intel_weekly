from __future__ import annotations

import unittest

from tests.phase4d_helpers import evaluate, lifecycle_event


class AlertBootstrapTests(unittest.TestCase):
    def test_history_is_watermarked_without_notifications(self) -> None:
        historical = [lifecycle_event(f"event-{index}", "lifecycle_initialized" if index < 5 else "extraction_improved") for index in range(6)]
        first = evaluate(run_id="run-1", started_at="2026-01-01T00:00:00+00:00", events=historical)
        self.assertEqual(6, first.state["bootstrap"]["lifecycle_event_watermark_count"])
        self.assertEqual([], first.new_events)
        second = evaluate(run_id="run-2", started_at="2026-01-02T00:00:00+00:00", events=historical, previous_alert_state=first.state, alert_events=first.all_events)
        self.assertEqual([], second.new_events)

    def test_only_new_event_notifies_after_bootstrap(self) -> None:
        historical = [lifecycle_event("old", "extraction_improved")]
        first = evaluate(run_id="run-1", started_at="2026-01-01T00:00:00+00:00", events=historical)
        new_events = [*historical, lifecycle_event("new", "item_discovered", "lifecycle-new")]
        second = evaluate(run_id="run-2", started_at="2026-01-02T00:00:00+00:00", events=new_events, previous_alert_state=first.state, alert_events=first.all_events)
        self.assertEqual(["notify"], [item["action"] for item in second.new_events])


if __name__ == "__main__":
    unittest.main()
