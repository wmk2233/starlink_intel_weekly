from __future__ import annotations

import unittest

from scripts.operational_health import build_run_health_data
from tests.phase4d_helpers import context, item_report, policy, source_status


def build(phase: str, history=None, **statuses):
    run_context = context("phase-run", "2026-01-01T00:00:00+00:00", **statuses)
    run_context["health_phase"] = phase
    run_context.setdefault("core_run_status", "success")
    return build_run_health_data(
        source_status=source_status(),
        item_extraction_report=item_report(),
        lifecycle_report={"totals": {"new": 0, "changed": 0}, "attention_items": []},
        llm_audit={"llm_enabled": False, "llm_status": "skipped_disabled", "validation_status": "not_run"},
        alert_report={"totals": {}},
        run_context=run_context,
        previous_history=history or [],
        policy=policy(),
    )


class HealthPhaseTransitionTests(unittest.TestCase):
    def test_provisional_only_evaluates_internal_components(self) -> None:
        result = build("provisional")
        self.assertFalse(result.health["is_final"])
        self.assertIsNone(result.health["finalized_at"])
        self.assertEqual([], result.history)
        self.assertEqual("healthy", result.health["components"]["source_collection"]["status"])
        for name in ("output_validation", "project_audit", "email", "gitee_sync", "workflow_core"):
            component = result.health["components"][name]
            self.assertEqual("pending_at_render_time", component["status"])
            self.assertEqual("pending_at_render_time", component["component_status_source"])

    def test_final_uses_workflow_outcomes_and_appends_once(self) -> None:
        result = build(
            "final",
            output_check_status="success",
            project_audit_status="success",
            email_status="failure",
            gitee_status="success",
            core_run_status="success",
        )
        self.assertTrue(result.health["is_final"])
        self.assertEqual("final", result.health["health_phase"])
        self.assertEqual("degraded", result.health["overall_health"])
        self.assertEqual("healthy", result.health["components"]["output_validation"]["status"])
        self.assertEqual("degraded", result.health["components"]["email"]["status"])
        self.assertEqual("workflow_step_outcome", result.health["components"]["gitee_sync"]["component_status_source"])
        self.assertEqual(1, len(result.history))
        self.assertTrue(result.history[0]["is_final"])
        self.assertEqual("healthy", result.health["components"]["llm"]["status"])

    def test_final_unknown_outcome_cannot_report_healthy(self) -> None:
        result = build(
            "final",
            output_check_status="success",
            project_audit_status="success",
            email_status="success",
            gitee_status="success",
            core_run_status="unknown",
        )
        self.assertEqual("unknown", result.health["components"]["workflow_core"]["status"])
        self.assertEqual("degraded", result.health["overall_health"])


if __name__ == "__main__":
    unittest.main()
