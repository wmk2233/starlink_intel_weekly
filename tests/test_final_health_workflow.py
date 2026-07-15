from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class FinalHealthWorkflowTests(unittest.TestCase):
    def test_workflow_orders_finalization_after_distribution(self) -> None:
        text = (ROOT / ".github" / "workflows" / "weekly.yml").read_text(encoding="utf-8")
        ordered = [
            "id: core_run",
            "id: output_check",
            "id: project_audit",
            "id: send_email",
            "id: github_commit",
            "id: gitee_sync",
            "id: finalize_health",
            "id: final_health_validation",
            "id: print_summary",
        ]
        positions = [text.index(value) for value in ordered]
        self.assertEqual(sorted(positions), positions)
        self.assertIn("python scripts/check_outputs.py --pre-finalize --strict", text)
        self.assertIn("python scripts/check_outputs.py --final-health-only --strict", text)
        self.assertIn("python scripts/build_run_health.py --phase final", text)
        self.assertIn("--no-email --output-mode dual", text)
        self.assertNotIn("git add .", text)

    def test_only_distribution_failures_are_non_blocking(self) -> None:
        text = (ROOT / ".github" / "workflows" / "weekly.yml").read_text(encoding="utf-8")
        send_block = text[text.index("id: send_email"):text.index("id: github_commit")]
        output_block = text[text.index("id: output_check"):text.index("id: project_audit")]
        audit_block = text[text.index("id: project_audit"):text.index("id: send_email")]
        self.assertIn("continue-on-error: true", send_block)
        self.assertNotIn("continue-on-error", output_block)
        self.assertNotIn("continue-on-error", audit_block)
        self.assertIn('echo "result=failure" >> "$GITHUB_OUTPUT"', text)
        self.assertIn("exit 0", text)


if __name__ == "__main__":
    unittest.main()
