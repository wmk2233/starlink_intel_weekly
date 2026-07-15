from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from parsers.common import detect_javascript_shell, detail_parse_error  # noqa: E402
from parsers.starlink_updates import parse_official_item  # noqa: E402


URL = "https://starlink.com/updates/fixture-item"
EVIDENCE = (
    "This fictional official fixture paragraph contains enough source text to test deterministic detail parsing "
    "without asserting any real Starlink event, product, date, or technical fact."
)


class DetailStaticParsingTests(unittest.TestCase):
    def test_json_ld_headline_has_priority(self) -> None:
        html = f'<script type="application/ld+json">{{"headline":"JSON Title","description":"{EVIDENCE}"}}</script><h1>H1 Title</h1>'
        item = parse_official_item(html, URL)
        self.assertEqual(item.title, "JSON Title")
        self.assertEqual(item.field_evidence["title"], "static_json_ld_headline")

    def test_h1_title_fallback(self) -> None:
        item = parse_official_item(f"<main><h1>Fixture H1</h1><p>{EVIDENCE}</p></main>", URL)
        self.assertEqual(item.title, "Fixture H1")

    def test_twitter_title_fallback(self) -> None:
        html = f'<meta name="twitter:title" content="Twitter Fixture"><main><p>{EVIDENCE}</p></main>'
        item = parse_official_item(html, URL)
        self.assertEqual(item.title, "Twitter Fixture")
        self.assertEqual(item.field_evidence["title"], "static_twitter_title")

    def test_published_and_modified_dates_are_separate(self) -> None:
        html = f'<script type="application/ld+json">{{"headline":"Dates","datePublished":"2026-01-01","dateModified":"2026-01-02","description":"{EVIDENCE}"}}</script>'
        item = parse_official_item(html, URL)
        self.assertTrue(item.published_at.startswith("2026-01-01"))
        self.assertTrue(item.modified_at.startswith("2026-01-02"))

    def test_date_is_not_inferred_from_slug(self) -> None:
        item = parse_official_item(f"<main><h1>No Date</h1><p>{EVIDENCE}</p></main>", "https://starlink.com/updates/2026-01-01-fixture")
        self.assertIsNone(item.published_at)

    def test_article_evidence_method(self) -> None:
        item = parse_official_item(f"<article><h1>Article</h1><p>{EVIDENCE}</p></article>", URL)
        self.assertEqual(item.field_evidence["evidence"], "static_article")

    def test_main_evidence_fallback(self) -> None:
        item = parse_official_item(f"<main><h1>Main</h1><p>{EVIDENCE}</p></main>", URL)
        self.assertEqual(item.field_evidence["evidence"], "static_main")

    def test_cookie_and_footer_text_are_excluded(self) -> None:
        html = f"<nav>Cookie settings privacy terms repeated navigation</nav><main><h1>Clean</h1><p>{EVIDENCE}</p></main><footer>Legal privacy cookie footer</footer>"
        item = parse_official_item(html, URL)
        self.assertNotIn("Legal privacy", item.evidence)

    def test_javascript_shell_is_detected(self) -> None:
        self.assertTrue(detect_javascript_shell('<html><body><div id="root"></div><script src="app.js"></script></body></html>'))

    def test_short_evidence_requests_fallback(self) -> None:
        html = "<main><h1>Fixture</h1><p>Too short.</p></main>"
        item = parse_official_item(html, URL)
        self.assertIsNone(item)
        self.assertEqual(detail_parse_error(html, item), "missing_evidence")


if __name__ == "__main__":
    unittest.main()
