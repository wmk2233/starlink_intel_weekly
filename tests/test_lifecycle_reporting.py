from __future__ import annotations

import unittest
import sys
from pathlib import Path

from scripts.item_lifecycle import build_lifecycle_update_plan
from tests.lifecycle_helpers import complete_observation, item

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from run_weekly import render_lifecycle_details, render_lifecycle_summary  # noqa: E402


class LifecycleReportingTests(unittest.TestCase):
    def test_summary_and_details_contain_required_sections(self) -> None:
        old = item()
        plan = build_lifecycle_update_plan([old], [old], complete_observation(), run_id="report-init")
        summary = render_lifecycle_summary(plan.lifecycle_report)
        details = render_lifecycle_details(
            plan.updated_lifecycle_state,
            plan.lifecycle_report,
            plan.all_versions,
        )
        for heading in [
            "### 本轮新增条目",
            "### 本轮内容变化",
            "### 解析质量提升",
            "### 暂时消失与长期未见",
            "### 详情抓取失败与恢复",
            "### 历史版本",
        ]:
            self.assertIn(heading, summary)
        self.assertIn("本轮未产生新增、语义变化、暂时消失、连续失败或恢复事件。", summary)
        self.assertIn("## 条目生命周期状态", details)
        self.assertIn("## 本轮生命周期事件", details)
        self.assertIn("## 结构化版本历史", details)
        self.assertNotIn("Existing official evidence.", details)


if __name__ == "__main__":
    unittest.main()
