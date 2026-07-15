from __future__ import annotations

import unittest
from unittest.mock import patch

from scripts.operational_health import upsert_run_health_history
from scripts.run_weekly import append_run_history


class HealthHistoryUpsertTests(unittest.TestCase):
    def test_final_replaces_provisional_in_place_and_migrates_legacy(self) -> None:
        rows = [
            {"run_id": "old", "generated_at": "2025-12-01T00:00:00+00:00", "overall_health": "healthy"},
            {"run_id": "target", "generated_at": "2026-01-01T00:00:00+00:00", "health_phase": "provisional", "is_final": False},
        ]
        final = {
            "run_id": "target",
            "generated_at": "2026-01-01T00:10:00+00:00",
            "health_phase": "final",
            "is_final": True,
            "finalized_at": "2026-01-01T00:10:00+00:00",
            "overall_health": "healthy",
        }
        result = upsert_run_health_history(rows, final, max_records=10)
        self.assertEqual(["old", "target"], [row["run_id"] for row in result])
        self.assertTrue(all(row["is_final"] for row in result))
        self.assertEqual("final", result[1]["health_phase"])

    def test_final_retry_does_not_duplicate_and_retention_stays_unique(self) -> None:
        final = {"run_id": "same", "generated_at": "2026-01-01T00:00:00+00:00", "health_phase": "final", "is_final": True}
        first = upsert_run_health_history([], final, max_records=2)
        second = upsert_run_health_history(first, {**final, "overall_health": "degraded"}, max_records=2)
        third = upsert_run_health_history(second, {"run_id": "next", "generated_at": "2026-01-02T00:00:00+00:00", "health_phase": "final", "is_final": True}, max_records=2)
        self.assertEqual(1, sum(row["run_id"] == "same" for row in second))
        self.assertEqual("degraded", second[0]["overall_health"])
        self.assertEqual(2, len(third))
        self.assertEqual(len(third), len({row["run_id"] for row in third}))

    def test_run_history_retries_upsert_same_run_id(self) -> None:
        meta = {
            "iso_week": "2026-W01",
            "run_iso": "2026-01-01T00:00:00+00:00",
            "output_mode": "dual",
            "send_email": "否",
            "collect_sources": "是",
            "connected_source_count": "0",
            "reachable_source_count": "0",
            "new_items": "0",
            "changed_items": "0",
            "unchanged_items": "0",
            "summary_path": "weekly/2026-W01-summary.md",
            "details_path": "weekly/2026-W01-details.md",
            "index_path": "weekly/2026-W01.md",
            "weekly_archive_index_path": "weekly/index.md",
            "weekly_manifest_path": "data/weekly_manifest.json",
        }
        with patch.dict("os.environ", {"RUN_ID": "same-run"}, clear=False), patch(
            "scripts.run_weekly.load_run_history", return_value=[{"run_id": "same-run", "old": True}]
        ), patch("scripts.run_weekly.write_run_history") as writer:
            append_run_history(meta, {}, False, 200)
        rows = writer.call_args.args[0]
        self.assertEqual(1, len(rows))
        self.assertEqual("same-run", rows[0]["run_id"])
        self.assertNotIn("old", rows[0])


if __name__ == "__main__":
    unittest.main()
