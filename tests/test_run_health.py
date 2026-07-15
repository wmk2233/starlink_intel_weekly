from __future__ import annotations

import unittest

from scripts.operational_health import build_run_health_data
from tests.phase4d_helpers import context, item_report, policy, source_status


class RunHealthTests(unittest.TestCase):
    def build(self, alert_totals=None, llm=None, **statuses):
        return build_run_health_data(
            source_status=source_status(),
            item_extraction_report=item_report(),
            lifecycle_report={"totals": {"new": 0, "changed": 0, "detail_fetch_failed": 0}, "attention_items": []},
            llm_audit=llm or {"llm_status": "skipped_disabled", "validation_status": "not_run"},
            alert_report={"totals": alert_totals or {}},
            run_context=context(
                "run",
                "2026-01-01T00:00:00+00:00",
                **{"core_run_status": "success", **statuses},
            ),
            previous_history=[],
            policy=policy(),
        )

    def test_healthy_and_llm_disabled_is_healthy(self) -> None:
        result = self.build()
        self.assertEqual("healthy", result.health["overall_health"])
        self.assertEqual("healthy", result.health["components"]["llm"]["status"])

    def test_warning_degrades_and_critical_is_unhealthy(self) -> None:
        warning = self.build({"open_warning": 1})
        critical = self.build({"open_critical": 1})
        self.assertEqual("degraded", warning.health["overall_health"])
        self.assertEqual("unhealthy", critical.health["overall_health"])

    def test_output_failure_is_unhealthy(self) -> None:
        result = self.build(output_check_status="failed")
        self.assertEqual("unhealthy", result.health["overall_health"])


if __name__ == "__main__":
    unittest.main()
