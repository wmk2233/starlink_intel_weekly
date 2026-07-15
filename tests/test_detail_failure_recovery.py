from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from collect_sources import _reuse_previous_success, apply_official_item_baseline_metadata  # noqa: E402


def old_record() -> dict[str, object]:
    return {
        "id": "old-id",
        "source_id": "starlink_official_updates",
        "record_scope": "item",
        "canonical_url": "https://starlink.com/updates/old",
        "url": "https://starlink.com/updates/old",
        "title": "Old fixture",
        "evidence": "Historical fictional evidence retained only for deterministic recovery testing.",
        "content_hash": "semantic-old",
        "semantic_content_hash": "semantic-old",
        "change_status": "unchanged",
        "fetched_at": "2026-01-01T00:00:00+00:00",
    }


class DetailFailureRecoveryTests(unittest.TestCase):
    def test_old_item_is_retained_on_failure(self) -> None:
        reused = _reuse_previous_success(old_record(), "2026-01-02T00:00:00+00:00", "render_timeout")
        self.assertEqual(reused["title"], "Old fixture")

    def test_failure_does_not_change_semantic_hash(self) -> None:
        reused = _reuse_previous_success(old_record(), "2026-01-02T00:00:00+00:00", "render_timeout")
        self.assertEqual(reused["semantic_content_hash"], "semantic-old")

    def test_consecutive_failures_increment(self) -> None:
        state = {"bootstrap_completed": True, "items": {"old-id": {"consecutive_failures": 2}}}
        diagnostic = {"record_id": "old-id", "canonical_url": "https://starlink.com/updates/old", "final_status": "failed", "error_type": "render_timeout", "checked_at": "2026-01-02T00:00:00+00:00"}
        apply_official_item_baseline_metadata([], {}, state, False, detail_diagnostics=[diagnostic])
        self.assertEqual(state["items"]["old-id"]["consecutive_failures"], 3)

    def test_success_resets_consecutive_failures(self) -> None:
        item = old_record()
        item.update({"parser_version": "starlink_updates_item_v2", "extraction_hash": "x", "last_detail_success_at": "2026-01-02T00:00:00+00:00"})
        state = {"bootstrap_completed": True, "items": {"old-id": {"consecutive_failures": 2}}}
        apply_official_item_baseline_metadata([item], {"old-id": old_record()}, state, True)
        self.assertEqual(state["items"]["old-id"]["consecutive_failures"], 0)

    def test_reuse_marker_is_set(self) -> None:
        reused = _reuse_previous_success(old_record(), "2026-01-02T00:00:00+00:00", "render_timeout")
        self.assertTrue(reused["current_run_data_reused"])

    def test_no_history_returns_none(self) -> None:
        self.assertIsNone(_reuse_previous_success(None, "2026-01-02T00:00:00+00:00", "render_timeout"))

    def test_temporary_failure_is_not_changed(self) -> None:
        reused = _reuse_previous_success(old_record(), "2026-01-02T00:00:00+00:00", "request_timeout")
        self.assertEqual(reused["change_status"], "unchanged")

    def test_temporary_failure_is_not_deleted(self) -> None:
        reused = _reuse_previous_success(old_record(), "2026-01-02T00:00:00+00:00", "http_4xx")
        self.assertNotIn("deleted", reused.values())

    def test_parser_failure_keeps_fields(self) -> None:
        original = old_record()
        reused = _reuse_previous_success(original, "2026-01-02T00:00:00+00:00", "parse_error")
        self.assertEqual(reused["evidence"], original["evidence"])

    def test_no_state_update_when_disabled(self) -> None:
        state = {"bootstrap_completed": True, "items": {}}
        before = copy.deepcopy(state)
        diagnostic = {"record_id": "x", "canonical_url": "https://starlink.com/updates/x", "final_status": "failed", "error_type": "render_timeout"}
        apply_official_item_baseline_metadata([], {}, state, False, detail_diagnostics=[diagnostic], update_state=False)
        self.assertEqual(state, before)

    def test_first_success_after_known_candidate_failure_is_not_new(self) -> None:
        recovered = old_record()
        recovered["parser_version"] = "starlink_updates_item_v2"
        state = {
            "bootstrap_completed": True,
            "items": {
                "old-id": {
                    "last_failure_at": "2026-01-01T00:00:00+00:00",
                    "last_error_type": "javascript_shell",
                    "consecutive_failures": 1,
                }
            },
        }
        apply_official_item_baseline_metadata([recovered], {}, state, True)
        self.assertEqual(recovered["change_status"], "unchanged")
        self.assertEqual(recovered["extraction_change_status"], "improved")
        self.assertEqual(recovered["change_reason"], "detail_failure_recovered")


if __name__ == "__main__":
    unittest.main()
