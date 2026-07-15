from __future__ import annotations

import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

import scripts.print_action_summary as action_summary


def final_health() -> dict:
    components = {
        name: {
            "status": "healthy",
            "result": "success",
            "component_status_source": "workflow_step_outcome" if name in {"output_validation", "project_audit", "email", "gitee_sync", "workflow_core"} else "internal_result",
        }
        for name in (
            "source_collection", "candidate_discovery", "detail_extraction", "lifecycle", "llm",
            "output_validation", "project_audit", "email", "gitee_sync", "workflow_core",
        )
    }
    return {
        "run_id": "final-run",
        "health_phase": "final",
        "is_final": True,
        "finalized_at": "2026-01-01T00:10:00+00:00",
        "overall_health": "healthy",
        "components": components,
    }


class Phase4D1ReportingTests(unittest.TestCase):
    def render(self, health: dict) -> str:
        alert = {"run_id": "final-run", "evaluation_phase": "final", "is_final": True, "overall_alert_status": "normal", "totals": {}}

        def json_file(path):
            if path.name == "run_health.json":
                return health
            if path.name == "alert_report.json":
                return alert
            return {}

        with patch.object(action_summary, "_json_file", side_effect=json_file), patch.object(action_summary, "_jsonl_file", return_value=[]), patch.object(action_summary, "_source_statuses", return_value=(False, {})), patch.object(action_summary, "_extraction_quality", return_value=(False, {})):
            output = io.StringIO()
            with redirect_stdout(output):
                action_summary.main()
            return output.getvalue()

    def test_summary_prefers_final_health(self) -> None:
        text = self.render(final_health())
        self.assertIn("Final health：available", text)
        self.assertIn("Health phase：final", text)
        self.assertIn("output_validation | healthy | success | workflow_step_outcome", text)

    def test_summary_does_not_promote_provisional_to_final(self) -> None:
        health = {**final_health(), "health_phase": "provisional", "is_final": False, "finalized_at": None}
        text = self.render(health)
        self.assertIn("Final health：unavailable", text)
        self.assertIn("final health unavailable", text)
        self.assertNotIn("整体健康状态：healthy", text)


if __name__ == "__main__":
    unittest.main()
