from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.run_weekly import (
    render_alert_details,
    render_health_trends,
    render_replay_acceptance,
    render_run_health_and_alerts,
)
from scripts.send_email import build_message


class Phase4DReportingTests(unittest.TestCase):
    def test_summary_health_and_alert_safety_wording(self) -> None:
        health = {"overall_health": "healthy", "components": {"llm": {"status": "healthy", "enabled": False}}}
        alerts = {"overall_alert_status": "normal", "totals": {}}
        text = render_run_health_and_alerts(health, alerts)
        self.assertIn("整体运行健康", text)
        self.assertIn("本轮未产生需要人工处理的运维告警", text)
        self.assertIn("人工复查优先级", text)

    def test_details_show_alerts_trends_and_replay_without_full_evidence(self) -> None:
        alert_text = render_alert_details({"alerts_this_run": [], "open_alerts": []})
        trend_text = render_health_trends([{"generated_at": "2026-01-01", "overall_health": "healthy"}])
        replay_text = render_replay_acceptance({"scenario_count": 13, "passed": 13, "failed": 0, "network_accessed": False, "production_files_modified": False})
        self.assertIn("本轮无运维告警", alert_text)
        self.assertIn("healthy", trend_text)
        self.assertIn("场景数量：13", replay_text)

    def test_email_keeps_two_markdown_attachments_and_safety_note(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            summary = root / "summary.md"
            details = root / "details.md"
            summary.write_text("# Synthetic summary", encoding="utf-8")
            details.write_text("# Synthetic details", encoding="utf-8")
            message = build_message(
                summary,
                "2026-W01",
                {"MAIL_TO": "to@example.invalid", "MAIL_FROM": "from@example.invalid"},
                collection_context={"overall_health": "healthy"},
                attachment_paths=[summary, details],
            )
            attachments = list(message.iter_attachments())
            self.assertEqual(2, len(attachments))
            self.assertIn("人工复查优先级", message.get_body(preferencelist=("plain",)).get_content())


if __name__ == "__main__":
    unittest.main()
