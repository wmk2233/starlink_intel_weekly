from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.run_weekly import render_run_health_and_alerts
from scripts.send_email import build_context_from_outputs, build_message


class PendingDistributionStatusTests(unittest.TestCase):
    def test_weekly_snapshot_uses_pending_not_unknown(self) -> None:
        pending = {"status": "pending_at_render_time", "component_status_source": "pending_at_render_time"}
        health = {
            "health_phase": "provisional",
            "is_final": False,
            "overall_health": "healthy",
            "components": {"email": pending, "gitee_sync": pending},
        }
        text = render_run_health_and_alerts(health, {"totals": {}})
        self.assertIn("pending_at_render_time", text)
        self.assertIn("pending_at_render_time 不是失败", text)
        self.assertIn("最终状态以 GitHub Actions Summary", text)

    def test_email_does_not_claim_its_own_success(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            summary = Path(directory) / "2026-W01-summary.md"
            summary.write_text("# Synthetic", encoding="utf-8")
            message = build_message(
                summary,
                "2026-W01",
                {"MAIL_TO": "to@example.invalid", "MAIL_FROM": "from@example.invalid"},
                collection_context={
                    "health_output_validation": "healthy",
                    "health_project_audit": "healthy",
                    "health_email": "pending_at_render_time",
                    "health_gitee_sync": "pending_at_render_time",
                },
            )
            body = message.get_body(preferencelist=("plain",)).get_content()
            self.assertIn("当前邮件投递状态：发送完成后由最终运行健康报告记录", body)
            self.assertIn("Gitee 同步状态：同步完成后由最终运行健康报告记录", body)
            self.assertNotIn("邮件发送成功", body)
            self.assertNotIn("邮件：unknown", body)

    def test_email_context_ignores_stale_alerts_and_reads_nested_llm_usage(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data_dir = Path(directory)
            summary = data_dir / "2026-W01-summary.md"
            summary.write_text("# Synthetic", encoding="utf-8")
            (data_dir / "run_health.json").write_text(
                json.dumps({"run_id": "current-run", "health_phase": "provisional"}),
                encoding="utf-8",
            )
            (data_dir / "alert_report.json").write_text(
                json.dumps({"run_id": "old-run", "overall_alert_status": "critical", "totals": {"critical": 9}}),
                encoding="utf-8",
            )
            (data_dir / "llm_audit.json").write_text(
                json.dumps({"llm_provider": "deepseek", "usage": {"prompt_tokens": 17, "total_tokens": 23}}),
                encoding="utf-8",
            )
            with patch("scripts.send_email.DATA_DIR", data_dir):
                context = build_context_from_outputs(summary, "2026-W01")

            self.assertEqual(context["overall_alert_status"], "pending_at_render_time")
            self.assertEqual(context["alert_critical"], "0")
            self.assertEqual(context["llm_provider"], "deepseek")
            self.assertEqual(context["llm_prompt_tokens"], "17")
            self.assertEqual(context["llm_total_tokens"], "23")


if __name__ == "__main__":
    unittest.main()
