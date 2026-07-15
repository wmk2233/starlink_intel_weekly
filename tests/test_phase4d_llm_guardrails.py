from __future__ import annotations

import json
import unittest

from scripts.llm_summarize import build_user_prompt, system_prompt
from tests.lifecycle_helpers import item


class Phase4DLLMGuardrailTests(unittest.TestCase):
    def test_system_prompt_keeps_operations_out_of_official_facts(self) -> None:
        prompt = system_prompt()
        for phrase in [
            "运维告警和运行健康",
            "不代表内容重要性",
            "不得写成官方服务中断",
            "分发链路问题",
            "不代表官方服务恢复",
        ]:
            self.assertIn(phrase, prompt)

    def test_user_prompt_contains_guardrails_but_no_alert_payload(self) -> None:
        record = item(url="https://example.invalid/updates/item-a")
        payload = json.loads(build_user_prompt([record]))
        constraints = payload["source_constraints"]
        self.assertTrue(constraints["operational_alerts_are_not_official_facts"])
        self.assertNotIn("alert_report", payload)
        self.assertNotIn("run_health", payload)


if __name__ == "__main__":
    unittest.main()
