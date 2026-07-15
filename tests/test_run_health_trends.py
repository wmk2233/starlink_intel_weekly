from __future__ import annotations

import unittest

from tests.phase4d_helpers import FIXTURE_SOURCE, evaluate, item_report, source_status


class RunHealthTrendTests(unittest.TestCase):
    def history(self, count=4):
        return [{"run_id": f"h-{index}", "generated_at": f"2025-12-{index + 1:02d}T00:00:00+00:00", "candidate_counts": {FIXTURE_SOURCE: 8}, "candidate_complete": {FIXTURE_SOURCE: True}} for index in range(count)]

    def test_candidate_collapse_requires_two_runs(self) -> None:
        first = evaluate(run_id="run-1", started_at="2026-01-01T00:00:00+00:00", sources=source_status(candidate_count=1), history=self.history())
        self.assertFalse(any(item.get("alert_type") == "candidate_discovery_degraded" for item in first.new_events))
        second = evaluate(run_id="run-2", started_at="2026-01-02T00:00:00+00:00", sources=source_status(candidate_count=1), history=self.history(), previous_alert_state=first.state, alert_events=first.all_events)
        self.assertTrue(any(item.get("alert_type") == "candidate_discovery_degraded" for item in second.new_events))

    def test_incomplete_candidates_do_not_alert(self) -> None:
        result = evaluate(run_id="run", started_at="2026-01-01T00:00:00+00:00", sources=source_status(candidate_count=0, complete=False), history=self.history())
        self.assertFalse(any(item.get("alert_type") == "candidate_discovery_degraded" for item in result.new_events))

    def test_detail_rate_requires_consecutive_runs_and_resolves(self) -> None:
        first = evaluate(run_id="run-1", started_at="2026-01-01T00:00:00+00:00", details=item_report(0, 4))
        second = evaluate(run_id="run-2", started_at="2026-01-02T00:00:00+00:00", details=item_report(0, 4), previous_alert_state=first.state, alert_events=first.all_events)
        self.assertTrue(any(item.get("alert_type") == "detail_success_rate_degraded" for item in second.new_events))
        recovered = evaluate(run_id="run-3", started_at="2026-01-03T00:00:00+00:00", details=item_report(4, 0), previous_alert_state=second.state, alert_events=second.all_events)
        self.assertIn("resolve", [item["action"] for item in recovered.new_events])


if __name__ == "__main__":
    unittest.main()
