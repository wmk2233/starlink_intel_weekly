from __future__ import annotations

import unittest

from scripts.operational_health import default_alert_state
from tests.phase4d_helpers import evaluate


def initialized_state() -> dict:
    state = default_alert_state()
    state["bootstrap"] = {
        "initialized": True,
        "initialized_at": "2025-12-31T00:00:00+00:00",
        "lifecycle_event_watermark_count": 0,
    }
    return state


class FinalAlertEvaluationTests(unittest.TestCase):
    def test_provisional_is_preview_only(self) -> None:
        previous = initialized_state()
        result = evaluate(
            run_id="preview",
            started_at="2026-01-01T00:00:00+00:00",
            previous_alert_state=previous,
            statuses={"output_check_status": "failure"},
            phase="provisional",
        )
        self.assertFalse(result.write_allowed)
        self.assertEqual(previous, result.state)
        self.assertEqual([], result.all_events)
        self.assertTrue(result.report["provisional_preview"])

    def test_final_failures_open_expected_severities_and_retry_is_unique(self) -> None:
        statuses = {
            "output_check_status": "failure",
            "project_audit_status": "failure",
            "email_status": "failure",
            "gitee_status": "failure",
        }
        first = evaluate(
            run_id="final-run",
            started_at="2026-01-01T00:00:00+00:00",
            previous_alert_state=initialized_state(),
            statuses=statuses,
        )
        severities = {value["alert_type"]: value["severity"] for value in first.state["open_conditions"].values()}
        self.assertEqual("critical", severities["output_validation_failed"])
        self.assertEqual("critical", severities["project_audit_failed"])
        self.assertEqual("warning", severities["email_delivery_failed"])
        self.assertEqual("warning", severities["gitee_sync_failed"])
        retry = evaluate(
            run_id="final-run",
            started_at="2026-01-01T00:00:00+00:00",
            previous_alert_state=first.state,
            alert_events=first.all_events,
            statuses=statuses,
        )
        ids = [event["alert_event_id"] for event in retry.all_events]
        self.assertEqual(len(ids), len(set(ids)))
        recovered = evaluate(
            run_id="next-run",
            started_at="2026-01-02T00:00:00+00:00",
            previous_alert_state=retry.state,
            alert_events=retry.all_events,
            statuses={
                "output_check_status": "success",
                "project_audit_status": "success",
                "email_status": "success",
                "gitee_status": "success",
            },
        )
        self.assertEqual({}, recovered.state["open_conditions"])
        self.assertEqual(4, sum(event["action"] == "resolve" for event in recovered.new_events))


if __name__ == "__main__":
    unittest.main()
