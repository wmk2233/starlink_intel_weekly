from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from parsers.common import ParsedOfficialItem, parser_quality  # noqa: E402


def item(**overrides: object) -> ParsedOfficialItem:
    values = {
        "source_id": "starlink_official_updates",
        "canonical_url": "https://www.starlink.com/updates/example",
        "title": "Official Example",
        "published_at": None,
        "published_date_text": None,
        "summary": "Official summary",
        "evidence": "Official evidence paragraph with enough detail to identify the source-backed item without external facts.",
        "field_evidence": {"title": "h1", "evidence": "main text"},
        "parser_version": "starlink_updates_item_v1",
        "record_type": "official_update",
        "category": "starlink_update",
        "is_starlink_related": True,
        "relevance_reason": "official update",
        "starlink_relevance": "direct",
    }
    values.update(overrides)
    return ParsedOfficialItem(**values)


class ItemQualityTests(unittest.TestCase):
    def test_missing_title_is_low(self) -> None:
        self.assertEqual(parser_quality(item(title=""))[0], "low")

    def test_missing_evidence_is_low(self) -> None:
        self.assertEqual(parser_quality(item(evidence=""))[1], 0.35)

    def test_basic_item_is_medium(self) -> None:
        self.assertEqual(parser_quality(item())[0], "medium")

    def test_medium_score_is_bounded(self) -> None:
        score = parser_quality(item())[1]
        self.assertGreaterEqual(score, 0.65)
        self.assertLessEqual(score, 0.84)

    def test_complete_item_is_high(self) -> None:
        complete = item(
            published_at="2026-07-01T00:00:00+00:00",
            field_evidence={"title": "h1", "published_at": "json-ld", "summary": "meta", "evidence": "main"},
        )
        self.assertEqual(parser_quality(complete), ("high", 0.9))

    def test_warning_prevents_high(self) -> None:
        warned = item(
            published_at="2026-07-01T00:00:00+00:00",
            field_evidence={"title": "h1", "published_at": "json-ld", "summary": "meta", "evidence": "main"},
            extraction_warnings=["warning"],
        )
        self.assertEqual(parser_quality(warned)[0], "medium")


if __name__ == "__main__":
    unittest.main()
