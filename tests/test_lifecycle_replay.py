from __future__ import annotations

import unittest
from pathlib import Path

from scripts.replay_lifecycle_events import run_replay


class LifecycleReplayTests(unittest.TestCase):
    def test_all_thirteen_scenarios_pass_offline(self) -> None:
        fixture = Path(__file__).parent / "fixtures" / "lifecycle_replay"
        report = run_replay(fixture)
        self.assertEqual(13, report["scenario_count"])
        self.assertEqual(13, report["passed"])
        self.assertEqual(0, report["failed"])
        self.assertFalse(report["network_accessed"])
        self.assertFalse(report["production_files_modified"])


if __name__ == "__main__":
    unittest.main()
