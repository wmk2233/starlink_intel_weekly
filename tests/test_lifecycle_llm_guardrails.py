from __future__ import annotations

import json
import unittest

from scripts.llm_summarize import build_user_prompt, normalize_item, system_prompt
from tests.lifecycle_helpers import item


class LifecycleLlmGuardrailTests(unittest.TestCase):
    def test_system_prompt_contains_lifecycle_semantic_boundaries(self) -> None:
        prompt = system_prompt()
        for phrase in [
            "不一定表示官方本周发布",
            "不代表官方事实变化",
            "不代表官方删除",
            "不代表官方页面或业务故障",
            "不代表官方服务恢复",
            "不代表重新发布",
            "不得将 parser enrichment",
            "monitoring context URL",
        ]:
            self.assertIn(phrase, prompt)

    def test_lifecycle_fields_are_limited_and_reference_pair_stays_aligned(self) -> None:
        record = item()
        record["lifecycle_state"] = "active"
        record["lifecycle_events_this_run"] = ["detail_fetch_recovered"]
        record["semantic_change_evidence"] = {"title": {"before_excerpt": "A", "after_excerpt": "B"}}
        normalized = normalize_item(record)
        self.assertEqual("active", normalized["lifecycle_state"])
        payload = json.loads(build_user_prompt([normalized]))
        pair = payload["allowed_reference_pairs"][0]
        core = payload["final_core_records"][0]
        self.assertEqual(pair["record_id"], core["id"])
        self.assertEqual(pair["canonical_url"], core["canonical_url"])
        self.assertNotIn("monitoring_context", payload)


if __name__ == "__main__":
    unittest.main()
