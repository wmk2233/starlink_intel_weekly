from __future__ import annotations

import unittest
from pathlib import Path

from scripts.replay_lifecycle_events import PRODUCTION_DATA_DIR, _inside, load_fixture


class LifecycleReplaySafetyTests(unittest.TestCase):
    def test_production_data_directory_is_detected(self) -> None:
        self.assertTrue(_inside(PRODUCTION_DATA_DIR / "replay", PRODUCTION_DATA_DIR))

    def test_fixture_uses_invalid_domain(self) -> None:
        fixture = Path(__file__).parent / "fixtures" / "lifecycle_replay"
        first, second = load_fixture(fixture)
        self.assertTrue(first["canonical_url"].startswith("https://example.invalid/"))
        self.assertTrue(second["canonical_url"].startswith("https://example.invalid/"))


if __name__ == "__main__":
    unittest.main()
