from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from parsers.common import (  # noqa: E402
    ItemCandidate,
    candidates_from_dom_links,
    discover_candidates,
    merge_candidates,
    normalize_candidate_url,
    stable_item_id,
)
from parsers.spacex_launches import classify_starlink_relevance, parse_official_item as parse_launch  # noqa: E402
from parsers.starlink_updates import parse_official_item as parse_update  # noqa: E402


FIXTURES = ROOT / "tests" / "fixtures"


class CandidateDiscoveryTests(unittest.TestCase):
    def test_starlink_anchor_candidate(self) -> None:
        items = discover_candidates((FIXTURES / "starlink_index.html").read_text(), "starlink_official_updates", "https://www.starlink.com/updates")
        self.assertEqual([item.canonical_url for item in items], ["https://starlink.com/updates/network-update"])

    def test_spacex_json_ld_candidate(self) -> None:
        items = discover_candidates((FIXTURES / "spacex_index.html").read_text(), "spacex_official_launches", "https://www.spacex.com/launches")
        self.assertEqual(items[0].origin, "json_ld")

    def test_embedded_json_candidate(self) -> None:
        html = '<script id="__NEXT_DATA__" type="application/json">{"items":[{"url":"/updates/embedded","title":"Embedded Update"}]}</script>'
        items = discover_candidates(html, "starlink_official_updates", "https://www.starlink.com/updates")
        self.assertEqual(items[0].origin, "embedded_json")

    def test_external_domain_rejected(self) -> None:
        self.assertIsNone(normalize_candidate_url("starlink_official_updates", "https://www.starlink.com/updates", "https://example.com/updates/x"))

    def test_index_path_rejected(self) -> None:
        self.assertIsNone(normalize_candidate_url("spacex_official_launches", "https://www.spacex.com/launches", "/launches/"))

    def test_wrong_path_rejected(self) -> None:
        self.assertIsNone(normalize_candidate_url("spacex_official_launches", "https://www.spacex.com/launches", "/media/example"))

    def test_tracking_query_is_removed(self) -> None:
        url = normalize_candidate_url("spacex_official_launches", "https://www.spacex.com/launches", "/launches/x?utm_source=test")
        self.assertEqual(url, "https://www.spacex.com/launches/x")

    def test_dom_candidate_is_limited_to_allowed_path(self) -> None:
        rows = [{"href": "https://www.spacex.com/launches/x", "text": "Mission X", "context": "Official mission context"}]
        self.assertEqual(len(candidates_from_dom_links("spacex_official_launches", "https://www.spacex.com/launches", rows)), 1)

    def test_merge_preserves_first_order(self) -> None:
        first = ItemCandidate("spacex_official_launches", "https://www.spacex.com/launches/a", "A")
        second = ItemCandidate("spacex_official_launches", "https://www.spacex.com/launches/b", "B")
        self.assertEqual([item.title for item in merge_candidates([first, second])], ["A", "B"])

    def test_merge_deduplicates_canonical_url(self) -> None:
        first = ItemCandidate("spacex_official_launches", "https://www.spacex.com/launches/a", "A")
        second = ItemCandidate("spacex_official_launches", "https://www.spacex.com/launches/a", "A2", "longer evidence")
        self.assertEqual(len(merge_candidates([first, second])), 1)

    def test_stable_id_ignores_title(self) -> None:
        url = "https://www.spacex.com/launches/a"
        self.assertEqual(stable_item_id("spacex_official_launches", url), stable_item_id("spacex_official_launches", url))


class DetailParsingTests(unittest.TestCase):
    def test_starlink_required_fields(self) -> None:
        item = parse_update((FIXTURES / "starlink_detail.html").read_text(), "https://www.starlink.com/updates/network-update")
        self.assertIsNotNone(item)
        self.assertEqual(item.record_type, "official_update")

    def test_starlink_date_is_strictly_normalized(self) -> None:
        item = parse_update((FIXTURES / "starlink_detail.html").read_text(), "https://www.starlink.com/updates/network-update")
        self.assertTrue(item.published_at.startswith("2026-07-01"))

    def test_starlink_does_not_infer_from_slug(self) -> None:
        item = parse_update("<html><body><h1>Title only</h1></body></html>", "https://www.starlink.com/updates/2026-07-01-test")
        self.assertIsNone(item)

    def test_launch_direct_relevance(self) -> None:
        item = parse_launch((FIXTURES / "spacex_direct_detail.html").read_text(), "https://www.spacex.com/launches/starlink-test")
        self.assertEqual(item.starlink_relevance, "direct")

    def test_launch_targeting_requires_explicit_phrase(self) -> None:
        item = parse_launch((FIXTURES / "spacex_direct_detail.html").read_text(), "https://www.spacex.com/launches/starlink-test")
        self.assertEqual(item.structured_fields["mission_status"], "targeting")

    def test_launch_payload_count_requires_direct_context(self) -> None:
        item = parse_launch((FIXTURES / "spacex_direct_detail.html").read_text(), "https://www.spacex.com/launches/starlink-test")
        self.assertEqual(item.structured_fields["payload_count"], 20)

    def test_launch_incidental_relevance(self) -> None:
        item = parse_launch((FIXTURES / "spacex_incidental_detail.html").read_text(), "https://www.spacex.com/launches/example")
        self.assertEqual(item.starlink_relevance, "incidental")

    def test_launch_incidental_not_core_related(self) -> None:
        item = parse_launch((FIXTURES / "spacex_incidental_detail.html").read_text(), "https://www.spacex.com/launches/example")
        self.assertFalse(item.is_starlink_related)

    def test_launch_unknown_status_without_explicit_phrase(self) -> None:
        item = parse_launch((FIXTURES / "spacex_incidental_detail.html").read_text(), "https://www.spacex.com/launches/example")
        self.assertEqual(item.structured_fields["mission_status"], "unknown")

    def test_invalid_detail_url_is_rejected(self) -> None:
        self.assertIsNone(parse_launch((FIXTURES / "spacex_direct_detail.html").read_text(), "https://example.com/launches/x"))

    def test_relevance_does_not_use_slug(self) -> None:
        relevance = classify_starlink_relevance("Example Mission", ["Current mission evidence without the relevant name."])
        self.assertEqual(relevance[0], "not_direct")

    def test_field_evidence_is_present(self) -> None:
        item = parse_update((FIXTURES / "starlink_detail.html").read_text(), "https://www.starlink.com/updates/network-update")
        self.assertIn("evidence", item.field_evidence)


if __name__ == "__main__":
    unittest.main()
