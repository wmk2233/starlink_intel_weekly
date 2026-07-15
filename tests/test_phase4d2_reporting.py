from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import scripts.print_action_summary as action_summary
from scripts.run_weekly import (
    apply_email_reporting_mode,
    get_run_metadata,
    render_history_records,
    render_recent_run_summary,
    render_run_health_and_alerts,
)
from scripts.send_email import build_context_from_outputs, build_message


def final_health() -> dict:
    return {
        "run_id": "final-run",
        "health_phase": "final",
        "is_final": True,
        "finalized_at": "2026-01-01T00:10:00+00:00",
        "overall_health": "healthy",
        "components": {
            "output_validation": {
                "status": "healthy",
                "result": "success",
                "component_status_source": "workflow_step_outcome",
            },
            "project_audit": {
                "status": "healthy",
                "result": "success",
                "component_status_source": "workflow_step_outcome",
            },
        },
    }


def render_summary(health: dict, legacy_status: str = "unknown") -> str:
    def json_file(path: Path) -> dict:
        if path.name == "run_health.json":
            return health
        if path.name == "alert_report.json":
            return {
                "run_id": "final-run",
                "evaluation_phase": "final",
                "is_final": True,
                "overall_alert_status": "normal",
                "totals": {},
            }
        return {}

    environment = {
        "OUTPUT_CHECK_STATUS": legacy_status,
        "PROJECT_AUDIT_STATUS": legacy_status,
    }
    with (
        patch.dict(os.environ, environment, clear=False),
        patch.object(action_summary, "_json_file", side_effect=json_file),
        patch.object(action_summary, "_jsonl_file", return_value=[]),
        patch.object(action_summary, "_source_statuses", return_value=(False, {})),
        patch.object(action_summary, "_extraction_quality", return_value=(False, {})),
    ):
        output = io.StringIO()
        with redirect_stdout(output):
            action_summary.main()
        return output.getvalue()


class FinalSummaryConsistencyTests(unittest.TestCase):
    def test_final_health_success_drives_legacy_check_sections(self) -> None:
        text = render_summary(final_health())
        self.assertIn("### 输出质量检查\n\n- 检查状态：passed", text)
        self.assertIn("### 稳定性与配置审计\n\n- 审计状态：passed", text)

    def test_missing_final_health_is_unavailable(self) -> None:
        text = render_summary({})
        self.assertIn("### 输出质量检查\n\n- 检查状态：unavailable", text)
        self.assertIn("### 稳定性与配置审计\n\n- 审计状态：unavailable", text)

    def test_final_health_overrides_conflicting_legacy_environment(self) -> None:
        text = render_summary(final_health(), legacy_status="failed")
        self.assertIn("检查状态：passed", text)
        self.assertIn("审计状态：passed", text)
        self.assertNotIn("检查状态：failed", text)
        self.assertNotIn("审计状态：failed", text)


class EmailReportingRegressionTests(unittest.TestCase):
    def test_structured_outputs_restore_item_detail_and_source_reporting(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data_dir = Path(directory)
            summary = data_dir / "2026-W01-summary.md"
            summary.write_text("# Synthetic", encoding="utf-8")
            payloads = {
                "source_status.json": {
                    "sources": {
                        "fixture_source": {
                            "source_name": "Fixture Official Updates",
                            "reachable": True,
                            "change_status": "unchanged",
                            "new_items": 0,
                            "changed_items": 0,
                            "unchanged_items": 2,
                            "dominant_extracted_level": "item_level",
                            "dominant_source_quality": "high",
                        }
                    }
                },
                "item_extraction_report.json": {
                    "sources": {
                        "fixture_source": {
                            "source_name": "Fixture Official Updates",
                            "candidate_count_total": 2,
                            "item_level_items": 2,
                            "page_level_items": 0,
                            "baseline_items": 0,
                            "new_items": 0,
                            "changed_items": 0,
                            "unchanged_items": 2,
                            "dominant_extracted_level": "item_level",
                            "dominant_source_quality": "high",
                        }
                    }
                },
                "detail_extraction_diagnostics.json": {
                    "sources": {
                        "fixture_source": {
                            "source_name": "Fixture Official Updates",
                            "candidate_count": 2,
                            "static_success": 1,
                            "render_success": 1,
                            "reused_previous_success": 0,
                            "final_success": 2,
                            "final_failed": 0,
                            "success_rate": 1.0,
                            "failure_types": {},
                        }
                    }
                },
                "run_health.json": {"run_id": "current", "health_phase": "provisional", "components": {}},
                "alert_report.json": {"run_id": "current", "totals": {}},
                "lifecycle_report.json": {"totals": {}},
                "llm_audit.json": {"llm_enabled": False, "llm_status": "skipped_disabled"},
            }
            for name, payload in payloads.items():
                (data_dir / name).write_text(json.dumps(payload), encoding="utf-8")

            with patch("scripts.send_email.DATA_DIR", data_dir):
                context = build_context_from_outputs(summary, "2026-W01")
            message = build_message(
                summary,
                "2026-W01",
                {"MAIL_TO": "to@example.invalid", "MAIL_FROM": "from@example.invalid"},
                collection_context=context,
            )
            body = message.get_body(preferencelist=("plain",)).get_content()

            self.assertIn("Fixture Official Updates", context["source_overview"])
            self.assertNotIn("fixture_source", context["source_overview"])
            self.assertIn("页面变化 unchanged", context["source_overview"])
            self.assertIn("未变化 2", context["item_extraction_overview"])
            self.assertIn("最终成功 2", context["detail_extraction_overview"])
            self.assertNotIn("暂无官方条目抽取结果", body)
            self.assertNotIn("暂无官方详情解析结果", body)

    def test_workflow_email_step_is_reported_as_pending_not_disabled(self) -> None:
        meta = get_run_metadata(False, True, "dual")
        apply_email_reporting_mode(
            meta,
            send_email_enabled=False,
            no_email_requested=True,
            dry_run=False,
            github_actions=True,
        )
        text = render_recent_run_summary(meta)
        self.assertIn("邮件发送方式：GitHub Actions 后续独立步骤", text)
        self.assertIn("报告生成时邮件状态：pending_at_render_time", text)
        self.assertNotIn("是否发送邮件：否", text)
        history_text = render_history_records([meta])
        self.assertIn("邮件发送方式：GitHub Actions 后续独立步骤", history_text)
        self.assertNotIn("是否发送邮件：否", history_text)

        health_text = render_run_health_and_alerts(
            {
                "health_phase": "provisional",
                "is_final": False,
                "overall_health": "healthy",
                "components": {"email": {"status": "pending_at_render_time"}},
            },
            {"totals": {}},
        )
        self.assertIn("pending_at_render_time 不是失败", health_text)


if __name__ == "__main__":
    unittest.main()
