from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from collect_sources import extract_official_items, fetch_source, load_items, load_sources


SUPPORTED_SOURCE_IDS = {"starlink_official_updates", "spacex_official_launches"}


def _flatten(source_id: str, detail: dict[str, Any]) -> dict[str, Any]:
    static = detail.get("static", {}) if isinstance(detail.get("static"), dict) else {}
    render = detail.get("render", {}) if isinstance(detail.get("render"), dict) else {}
    return {
        "source_id": source_id,
        "canonical_url": detail.get("canonical_url"),
        "candidate_discovery_method": detail.get("discovery_method"),
        "static_http_status": static.get("http_status"),
        "static_content_type": static.get("content_type"),
        "static_html_length": static.get("html_length", 0),
        "static_redirect_count": static.get("redirect_count", 0),
        "static_final_host": static.get("final_host"),
        "static_parse_status": static.get("parse_status", "unknown_error"),
        "static_title_found": bool(static.get("title_found")),
        "static_date_found": bool(static.get("date_found")),
        "static_evidence_length": int(static.get("evidence_length") or 0),
        "static_parser_warning_types": list(static.get("parser_warning_types") or []),
        "render_attempted": bool(render.get("attempted")),
        "render_navigation_status": render.get("navigation_status", "not_attempted"),
        "render_final_host": render.get("final_host"),
        "rendered_dom_length": int(render.get("dom_length") or 0),
        "render_parse_status": render.get("parse_status", "not_attempted"),
        "render_title_found": bool(render.get("title_found")),
        "render_date_found": bool(render.get("date_found")),
        "render_evidence_length": int(render.get("evidence_length") or 0),
        "final_status": detail.get("final_status", "failed"),
        "final_error_type": detail.get("error_type"),
    }


def diagnose(
    source: dict[str, Any],
    *,
    limit: int,
    render_mode: str,
    timeout_ms: int,
    wait_ms: int,
    max_scrolls: int,
) -> list[dict[str, Any]]:
    fetch = fetch_source(source)
    if not fetch.reachable:
        return []
    existing = {str(item.get("id")): item for item in load_items() if item.get("id")}
    outcome = extract_official_items(
        fetch,
        limit,
        render_mode="auto",
        existing_items=existing,
        detail_render_mode=render_mode,
        max_rendered_details_per_source=limit,
        detail_timeout_ms=timeout_ms,
        detail_wait_ms=wait_ms,
        detail_max_scrolls=max_scrolls,
        detail_concurrency=1,
    )
    return [_flatten(str(source["id"]), detail) for detail in outcome.detail_diagnostics]


def print_text(records: list[dict[str, Any]]) -> None:
    for record in records:
        print(f"来源：{record['source_id']}")
        print(f"详情 URL：{record['canonical_url']}")
        print(f"静态解析：{record['static_parse_status']}")
        print(f"详情渲染：{record['render_parse_status']}")
        print(f"最终状态：{record['final_status']}")
        print(f"错误类型：{record['final_error_type'] or 'none'}")
        print()


def main() -> int:
    parser = argparse.ArgumentParser(description="对官方详情候选执行脱敏、无写入诊断。")
    parser.add_argument("--source-id", choices=sorted(SUPPORTED_SOURCE_IDS))
    parser.add_argument("--all", action="store_true", help="诊断 sources.yml 中全部已启用官方来源。")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--render-mode", choices=["auto", "never", "always"], default="auto")
    parser.add_argument("--detail-timeout-ms", type=int, default=30_000)
    parser.add_argument("--detail-wait-ms", type=int, default=1_500)
    parser.add_argument("--detail-max-scrolls", type=int, default=3)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--no-write", action="store_true", help="兼容显式无写入调用；本脚本始终不写文件。")
    args = parser.parse_args()

    if args.limit < 1 or args.detail_timeout_ms < 1 or args.detail_wait_ms < 0 or args.detail_max_scrolls < 0:
        print("limit/timeout 必须大于 0，wait/max-scrolls 不能小于 0。")
        return 2
    if not args.all and not args.source_id:
        parser.error("请指定 --all 或 --source-id。")

    selected = [
        source
        for source in load_sources()
        if source.get("enabled") is True
        and source.get("id") in SUPPORTED_SOURCE_IDS
        and (args.all or source.get("id") == args.source_id)
    ]
    records: list[dict[str, Any]] = []
    for source in selected:
        records.extend(
            diagnose(
                source,
                limit=args.limit,
                render_mode=args.render_mode,
                timeout_ms=args.detail_timeout_ms,
                wait_ms=args.detail_wait_ms,
                max_scrolls=args.detail_max_scrolls,
            )
        )
    if args.json:
        print(json.dumps(records, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print_text(records)
    return 0


if __name__ == "__main__":
    sys.exit(main())
