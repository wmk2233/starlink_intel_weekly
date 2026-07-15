from __future__ import annotations

import unittest

from tests.phase4d_helpers import evaluate, lifecycle_event


class AlertEventNotificationTests(unittest.TestCase):
    def test_supported_events_notify_once(self) -> None:
        first = evaluate(run_id="bootstrap", started_at="2026-01-01T00:00:00+00:00")
        event_types = ["item_discovered", "semantic_content_changed", "extraction_improved", "detail_fetch_recovered", "reappeared"]
        events = [lifecycle_event(f"event-{index}", name) for index, name in enumerate(event_types)]
        notified = evaluate(run_id="notify", started_at="2026-01-02T00:00:00+00:00", events=events, previous_alert_state=first.state)
        self.assertEqual(5, sum(item["action"] == "notify" for item in notified.new_events))
        retried = evaluate(run_id="notify", started_at="2026-01-02T00:00:00+00:00", events=events, previous_alert_state=notified.state, alert_events=notified.all_events)
        self.assertEqual([], retried.new_events)


if __name__ == "__main__":
    unittest.main()
