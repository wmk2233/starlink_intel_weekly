from __future__ import annotations

import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

import scripts.operational_health as operational_health
from scripts.operational_health import atomic_write_bundle, build_run_health_data
from tests.phase4d_helpers import context, evaluate, item_report, lifecycle_event, policy, source_status


class HistoryRetentionTests(unittest.TestCase):
    def test_processed_and_alert_events_are_bounded(self) -> None:
        bootstrap = evaluate(run_id="bootstrap", started_at="2026-01-01T00:00:00+00:00")
        events = [lifecycle_event(f"event-{index}") for index in range(8)]
        result = evaluate(run_id="run", started_at="2026-01-02T00:00:00+00:00", events=events, previous_alert_state=bootstrap.state, config={"max_processed_alert_event_ids": 3, "max_alert_events": 3})
        self.assertLessEqual(len(result.state["processed_event_ids"]), 3)
        self.assertLessEqual(len(result.all_events), 3)

    def test_health_history_is_bounded_and_run_id_upserts(self) -> None:
        old = [{"run_id": f"old-{index}", "generated_at": f"2025-12-{index + 1:02d}T00:00:00+00:00"} for index in range(5)]
        result = build_run_health_data(source_status=source_status(), item_extraction_report=item_report(), lifecycle_report={"totals": {}}, llm_audit={"llm_status": "skipped_disabled"}, alert_report={"totals": {}}, run_context=context("same", "2026-01-01T00:00:00+00:00"), previous_history=[*old, {"run_id": "same", "generated_at": "2025-12-31T00:00:00+00:00"}], policy=policy(max_run_health_records=3))
        self.assertEqual(3, len(result.history))
        self.assertEqual(1, sum(row["run_id"] == "same" for row in result.history))

    def test_atomic_bundle_failure_preserves_old_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "first.json"
            second = root / "second.json"
            first.write_text("old-first", encoding="utf-8")
            second.write_text("old-second", encoding="utf-8")
            real_replace = operational_health.os.replace
            failed = False

            def flaky(source, destination):
                nonlocal failed
                if not failed and Path(destination) == second:
                    failed = True
                    raise OSError("synthetic")
                return real_replace(source, destination)

            with self.assertRaises(OSError):
                with patch.object(operational_health.os, "replace", side_effect=flaky):
                    atomic_write_bundle({first: "new-first", second: "new-second"})
            self.assertEqual("old-first", first.read_text(encoding="utf-8"))
            self.assertEqual("old-second", second.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
