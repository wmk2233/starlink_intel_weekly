from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import requests
import yaml
from bs4 import BeautifulSoup

from parsers.common import discover_candidates


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCES_FILE = PROJECT_ROOT / "sources.yml"
USER_AGENT = "starlink-intel-weekly/phase4a (+official-source-monitoring)"
SUPPORTED = {"starlink_official_updates", "spacex_official_launches"}


def load_sources() -> list[dict[str, Any]]:
    payload = yaml.safe_load(SOURCES_FILE.read_text(encoding="utf-8")) or {}
    return [source for source in payload.get("sources", []) if source.get("enabled") is True]


def diagnose(source: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {
        "source_id": source.get("id"),
        "url": source.get("url"),
        "http_status": None,
        "html_length": 0,
        "script_types": [],
        "static_candidate_count": 0,
        "candidate_paths": [],
        "render_may_be_required": True,
        "error": None,
    }
    try:
        response = requests.get(
            str(source["url"]),
            headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"},
            timeout=20,
        )
        result["http_status"] = response.status_code
        response.raise_for_status()
    except requests.RequestException as exc:
        result["error"] = exc.__class__.__name__
        return result

    html = response.text
    soup = BeautifulSoup(html, "html.parser")
    candidates = discover_candidates(html, str(source["id"]), str(source["url"]))
    result["html_length"] = len(html.encode("utf-8"))
    result["script_types"] = sorted(
        {str(script.get("type") or "(none)") for script in soup.find_all("script")}
    )
    result["static_candidate_count"] = len(candidates)
    result["candidate_paths"] = [candidate.canonical_url for candidate in candidates[:5]]
    result["render_may_be_required"] = len(candidates) == 0
    return result


def print_text(results: list[dict[str, Any]]) -> None:
    for result in results:
        print(f"来源：{result['source_id']}")
        print(f"HTTP 状态：{result['http_status']}")
        print(f"HTML 长度：{result['html_length']}")
        print(f"script 类型：{', '.join(result['script_types']) or '无'}")
        print(f"静态候选数量：{result['static_candidate_count']}")
        print(f"候选路径（最多 5 条）：{result['candidate_paths']}")
        print(f"可能需要受控渲染：{'是' if result['render_may_be_required'] else '否'}")
        if result.get("error"):
            print(f"诊断错误：{result['error']}")
        print()


def main() -> int:
    parser = argparse.ArgumentParser(description="安全诊断两个官方索引页的静态条目发现能力。")
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--source-id", choices=sorted(SUPPORTED))
    selection.add_argument("--all", action="store_true")
    parser.add_argument("--json", action="store_true", help="输出 JSON。")
    parser.add_argument("--no-write", action="store_true", help="兼容显式只读调用；本脚本始终不写文件。")
    args = parser.parse_args()

    sources = [source for source in load_sources() if source.get("id") in SUPPORTED]
    if args.source_id:
        sources = [source for source in sources if source.get("id") == args.source_id]
    results = [diagnose(source) for source in sources]
    if args.json:
        print(json.dumps({"sources": results}, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print_text(results)
    return 0 if results else 2


if __name__ == "__main__":
    sys.exit(main())
