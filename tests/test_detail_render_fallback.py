from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from collect_sources import (  # noqa: E402
    DetailFetchResult,
    SourceFetch,
    _should_render_detail,
    extract_official_items,
)
from parsers.starlink_updates import parse_official_item  # noqa: E402


URL = "https://starlink.com/updates/render-fixture"
EVIDENCE = "A fictional rendered paragraph with enough deterministic evidence for parser testing and no real-world Starlink assertions or inferred facts."


def source_fetch() -> SourceFetch:
    source = {"id": "starlink_official_updates", "name": "Starlink Official Updates", "url": "https://www.starlink.com/updates"}
    html = '<a href="/updates/render-fixture">Fixture</a>'
    return SourceFetch(source, "2026-01-01T00:00:00+00:00", 200, True, html=html, page_text="Fixture")


def rendered_item():
    return parse_official_item(f"<main><h1>Rendered Fixture</h1><p>{EVIDENCE}</p></main>", URL, parse_method="rendered")


class DetailRenderFallbackTests(unittest.TestCase):
    def test_static_success_does_not_render(self) -> None:
        self.assertFalse(_should_render_detail(None, "auto", True))

    def test_javascript_shell_renders(self) -> None:
        self.assertTrue(_should_render_detail("javascript_shell", "auto", False))

    def test_missing_title_renders(self) -> None:
        self.assertTrue(_should_render_detail("missing_title", "auto", False))

    def test_missing_evidence_renders(self) -> None:
        self.assertTrue(_should_render_detail("missing_evidence", "auto", False))

    def test_invalid_url_does_not_render(self) -> None:
        self.assertFalse(_should_render_detail("invalid_candidate_url", "auto", False))

    def test_404_does_not_render(self) -> None:
        self.assertFalse(_should_render_detail("http_4xx", "auto", False))

    def test_rendered_success_generates_item(self) -> None:
        calls: list[str] = []

        def renderer(_source, candidates, _parser, **_kwargs):
            calls.extend(candidate.canonical_url for candidate in candidates)
            return {URL: {"item": rendered_item(), "error_type": None, "navigation_status": "success", "final_host": "starlink.com", "dom_length": 200, "detail_page_hash": "page"}}

        with patch("collect_sources.fetch_detail_html", return_value=DetailFetchResult(html='<div id="root"></div><script></script>', http_status=200, content_type="text/html", html_length=40, final_url=URL, final_host="starlink.com")):
            outcome = extract_official_items(source_fetch(), 10, detail_renderer=renderer)
        self.assertEqual(outcome.final_detail_success, 1)
        self.assertEqual(len(calls), 1)

    def test_rendered_missing_fields_fails(self) -> None:
        def renderer(_source, candidates, _parser, **_kwargs):
            return {candidate.canonical_url: {"item": None, "error_type": "rendered_missing_required_fields", "navigation_status": "success", "final_host": "starlink.com", "dom_length": 20, "detail_page_hash": None} for candidate in candidates}

        with patch("collect_sources.fetch_detail_html", return_value=DetailFetchResult(html='<div id="root"></div><script></script>', http_status=200, content_type="text/html", html_length=40, final_url=URL, final_host="starlink.com")):
            outcome = extract_official_items(source_fetch(), 10, detail_renderer=renderer)
        self.assertEqual(outcome.final_detail_failed, 1)

    def test_single_url_is_rendered_once(self) -> None:
        calls = 0

        def renderer(_source, candidates, _parser, **_kwargs):
            nonlocal calls
            calls += len(candidates)
            return {URL: {"item": rendered_item(), "error_type": None, "navigation_status": "success", "final_host": "starlink.com", "dom_length": 200, "detail_page_hash": "page"}}

        with patch("collect_sources.fetch_detail_html", return_value=DetailFetchResult(html='<div id="root"></div><script></script>', http_status=200, content_type="text/html", html_length=40, final_url=URL, final_host="starlink.com")):
            extract_official_items(source_fetch(), 10, detail_renderer=renderer)
        self.assertEqual(calls, 1)

    def test_render_limit_is_safe(self) -> None:
        with patch("collect_sources.fetch_detail_html", return_value=DetailFetchResult(html='<div id="root"></div><script></script>', http_status=200, content_type="text/html", html_length=40, final_url=URL, final_host="starlink.com")):
            outcome = extract_official_items(source_fetch(), 10, max_rendered_details_per_source=0)
        self.assertEqual(outcome.failure_types.get("render_limit_reached"), 1)


if __name__ == "__main__":
    unittest.main()
