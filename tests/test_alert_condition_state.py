from __future__ import annotations

import unittest

from tests.phase4d_helpers import evaluate, lifecycle_state, source_status


class AlertConditionStateTests(unittest.TestCase):
    def test_detail_failure_opens_once_and_cooldown_suppresses(self) -> None:
        first = evaluate(run_id="run-1", started_at="2026-01-01T00:00:00+00:00", state=lifecycle_state("fetch_failed", 1))
        self.assertIn("open", [item["action"] for item in first.new_events])
        second = evaluate(run_id="run-2", started_at="2026-01-01T01:00:00+00:00", state=lifecycle_state("fetch_failed", 2), previous_alert_state=first.state, alert_events=first.all_events)
        self.assertNotIn("open", [item["action"] for item in second.new_events])
        self.assertIn("suppress", [item["action"] for item in second.new_events])

    def test_source_unreachable_escalates_on_second_observation(self) -> None:
        first = evaluate(run_id="run-1", started_at="2026-01-01T00:00:00+00:00", sources=source_status(reachable=False))
        second = evaluate(run_id="run-2", started_at="2026-01-02T00:00:00+00:00", sources=source_status(reachable=False), previous_alert_state=first.state, alert_events=first.all_events)
        self.assertIn("escalate", [item["action"] for item in second.new_events])
        self.assertIn("high", [item["severity"] for item in second.state["open_conditions"].values()])

    def test_gitee_is_warning_and_output_validation_is_critical(self) -> None:
        result = evaluate(
            run_id="run",
            started_at="2026-01-01T00:00:00+00:00",
            statuses={"gitee_status": "failed", "output_check_status": "failed"},
        )
        severities = {item["alert_type"]: item["severity"] for item in result.state["open_conditions"].values()}
        self.assertEqual("warning", severities["gitee_sync_failed"])
        self.assertEqual("critical", severities["output_validation_failed"])


if __name__ == "__main__":
    unittest.main()
