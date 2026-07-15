from __future__ import annotations

import unittest

from tests.phase4d_helpers import evaluate, lifecycle_state


class AlertEscalationResolutionTests(unittest.TestCase):
    def test_failure_escalates_and_resolves_immediately(self) -> None:
        first = evaluate(run_id="run-1", started_at="2026-01-01T00:00:00+00:00", state=lifecycle_state("fetch_failed", 1))
        high = evaluate(run_id="run-2", started_at="2026-01-02T00:00:00+00:00", state=lifecycle_state("fetch_failed", 3), previous_alert_state=first.state, alert_events=first.all_events)
        self.assertIn("escalate", [item["action"] for item in high.new_events])
        resolved = evaluate(run_id="run-3", started_at="2026-01-03T00:00:00+00:00", state=lifecycle_state("active"), previous_alert_state=high.state, alert_events=high.all_events)
        self.assertIn("resolve", [item["action"] for item in resolved.new_events])
        self.assertEqual({}, resolved.state["open_conditions"])

    def test_resolved_condition_can_open_again(self) -> None:
        first = evaluate(run_id="a", started_at="2026-01-01T00:00:00+00:00", state=lifecycle_state("temporarily_missing"))
        resolved = evaluate(run_id="b", started_at="2026-01-02T00:00:00+00:00", state=lifecycle_state(), previous_alert_state=first.state, alert_events=first.all_events)
        reopened = evaluate(run_id="c", started_at="2026-01-03T00:00:00+00:00", state=lifecycle_state("temporarily_missing"), previous_alert_state=resolved.state, alert_events=resolved.all_events)
        self.assertIn("open", [item["action"] for item in reopened.new_events])

    def test_llm_validation_failure_escalates_and_generated_passed_resolves(self) -> None:
        state = None
        alert_events = []
        for index in range(1, 4):
            result = evaluate(
                run_id=f"llm-{index}",
                started_at=f"2026-01-0{index}T00:00:00+00:00",
                llm={"llm_status": "validation_failed", "validation_status": "failed"},
                previous_alert_state=state,
                alert_events=alert_events,
            )
            state, alert_events = result.state, result.all_events
        self.assertTrue(any(item.get("severity") == "high" for item in state["open_conditions"].values()))
        recovered = evaluate(
            run_id="llm-4",
            started_at="2026-01-04T00:00:00+00:00",
            llm={"llm_status": "generated", "validation_status": "passed"},
            previous_alert_state=state,
            alert_events=alert_events,
        )
        self.assertIn("resolve", [item["action"] for item in recovered.new_events])


if __name__ == "__main__":
    unittest.main()
