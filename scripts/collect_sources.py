from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urldefrag, urljoin, urlsplit, urlunsplit

import requests
import yaml
from bs4 import BeautifulSoup


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCES_FILE = PROJECT_ROOT / "sources.yml"
ITEMS_FILE = PROJECT_ROOT / "data" / "items.jsonl"
RAW_DIR = PROJECT_ROOT / "data" / "raw"
USER_AGENT = "Mozilla/5.0 starlink-intel-weekly/0.2"
COLLECTOR_NAME = "rule_based_html_v1"


@dataclass
class CollectResult:
    items: list[dict[str, Any]]
    sources: list[str]
    errors: list[str]
    new_count: int = 0
    updated_count: int = 0
    total_items: int = 0
    wrote_items: bool = False


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def load_sources(path: Path = SOURCES_FILE) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"来源配置文件不存在：{path}")

    with path.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}

    sources = data.get("sources", [])
    if not isinstance(sources, list):
        raise ValueError("sources.yml 格式错误：sources 必须是列表。")
    return sources


def load_items(path: Path = ITEMS_FILE) -> list[dict[str, Any]]:
    if not path.exists():
        return []

    items: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                item = json.loads(stripped)
            except json.JSONDecodeError:
                print(f"跳过无法解析的 JSONL 行：{path}:{line_number}")
                continue
            if isinstance(item, dict):
                items.append(item)
    return items


def write_items_upsert(new_items: list[dict[str, Any]], path: Path = ITEMS_FILE) -> tuple[int, int, int]:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing_items = load_items(path)
    by_id = {item.get("id"): item for item in existing_items if item.get("id")}

    new_count = 0
    updated_count = 0
    for item in new_items:
        item_id = item.get("id")
        if not item_id:
            continue
        if item_id in by_id:
            merged = dict(by_id[item_id])
            merged.update(item)
            by_id[item_id] = merged
            updated_count += 1
        else:
            by_id[item_id] = item
            new_count += 1

    ordered = sorted(
        by_id.values(),
        key=lambda item: str(item.get("fetched_at") or ""),
        reverse=True,
    )
    with path.open("w", encoding="utf-8", newline="\n") as file:
        for item in ordered:
            file.write(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n")

    return new_count, updated_count, len(ordered)


def make_item_id(url: str, title: str) -> str:
    digest = hashlib.sha256(f"{url}|{title}".encode("utf-8")).hexdigest()
    return digest[:16]


def normalize_url(href: str, base_url: str) -> str | None:
    if not href:
        return None

    absolute = urljoin(base_url, href.strip())
    absolute, _fragment = urldefrag(absolute)
    parts = urlsplit(absolute)
    if parts.scheme not in {"http", "https"}:
        return None

    normalized = urlunsplit((parts.scheme, parts.netloc, parts.path.rstrip("/") or "/", "", ""))
    return normalized


def is_updates_url(url: str) -> bool:
    parts = urlsplit(url)
    host = parts.netloc.lower()
    path = parts.path.lower()
    return host.endswith("starlink.com") and "/updates" in path


def clean_text(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", value).strip()


def title_from_slug(url: str) -> str:
    path = urlsplit(url).path.strip("/")
    if not path:
        return "Starlink Official Updates"
    slug = path.split("/")[-1] or "updates"
    words = re.sub(r"[-_]+", " ", slug).strip()
    if not words or words.lower() == "updates":
        return "Starlink Official Updates"
    return words.title()


def nearby_heading(link_node: Any) -> str:
    container = link_node.find_parent(["article", "section", "li", "div"])
    if not container:
        return ""
    heading = container.find(["h1", "h2", "h3", "h4"])
    return clean_text(heading.get_text(" ")) if heading else ""


def page_excerpt(soup: BeautifulSoup, min_length: int = 300, max_length: int = 500) -> str:
    for unwanted in soup(["script", "style", "noscript", "svg"]):
        unwanted.decompose()

    text = clean_text(soup.get_text(" "))
    if len(text) <= max_length:
        return text
    excerpt = text[:max_length].strip()
    if len(excerpt) < min_length:
        return text[:max_length].strip()
    return excerpt


def page_title(soup: BeautifulSoup) -> str:
    if soup.title and soup.title.string:
        return clean_text(soup.title.string)
    h1 = soup.find("h1")
    if h1:
        return clean_text(h1.get_text(" "))
    return "Starlink Official Updates"


def build_item(
    source: dict[str, Any],
    title: str,
    url: str,
    fetched_at: str,
    http_status: int | None,
    summary: str,
    evidence: str,
) -> dict[str, Any]:
    return {
        "id": make_item_id(url, title),
        "source_id": source["id"],
        "source_name": source["name"],
        "source_type": source.get("source_type"),
        "reliability_tier": source.get("reliability_tier"),
        "category": source.get("category"),
        "language": source.get("language"),
        "title": title,
        "url": url,
        "published_at": None,
        "fetched_at": fetched_at,
        "http_status": http_status,
        "tags": ["starlink", "official", "updates"],
        "summary": summary,
        "evidence": evidence,
        "collector": COLLECTOR_NAME,
    }


def save_raw_html(source_id: str, html: str, fetched_at: str) -> Path:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    safe_time = re.sub(r"[^0-9A-Za-z_-]+", "-", fetched_at)
    path = RAW_DIR / f"{source_id}-{safe_time}.html"
    path.write_text(html, encoding="utf-8", newline="\n")
    return path


def fetch_html(source: dict[str, Any], timeout: int = 20) -> tuple[int, str]:
    response = requests.get(
        source["url"],
        headers={"User-Agent": USER_AGENT},
        timeout=timeout,
    )
    response.raise_for_status()
    return response.status_code, response.text


def parse_starlink_updates(source: dict[str, Any], html: str, http_status: int | None, fetched_at: str, limit: int) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    title = page_title(soup)
    excerpt = page_excerpt(soup)

    items_by_id: dict[str, dict[str, Any]] = {}
    for link in soup.find_all("a", href=True):
        normalized = normalize_url(link.get("href", ""), source["url"])
        if not normalized or not is_updates_url(normalized):
            continue

        link_text = clean_text(link.get_text(" "))
        title_candidate = link_text or nearby_heading(link) or title_from_slug(normalized)
        evidence = clean_text(link_text or nearby_heading(link) or excerpt)
        summary = f"规则化采集发现 Starlink 官方 Updates 相关链接：{title_candidate}"
        item = build_item(
            source=source,
            title=title_candidate,
            url=normalized,
            fetched_at=fetched_at,
            http_status=http_status,
            summary=summary,
            evidence=evidence[:500],
        )
        items_by_id[item["id"]] = item

    if not items_by_id:
        summary = "规则化采集生成 Starlink Official Updates 页面级记录。未编造发布时间或具体技术事实。"
        item = build_item(
            source=source,
            title=title or "Starlink Official Updates 页面采集记录",
            url=source["url"],
            fetched_at=fetched_at,
            http_status=http_status,
            summary=summary,
            evidence=excerpt[:500],
        )
        items_by_id[item["id"]] = item

    return list(items_by_id.values())[:limit]


def collect_source(source: dict[str, Any], limit: int = 20, save_raw: bool = False, dry_run: bool = False) -> tuple[list[dict[str, Any]], str | None]:
    fetched_at = now_iso()
    try:
        http_status, html = fetch_html(source)
    except requests.RequestException as exc:
        message = f"{source.get('name', source.get('id'))} 采集失败：{exc.__class__.__name__}"
        print(message)
        return [], message

    if save_raw and not dry_run:
        raw_path = save_raw_html(source["id"], html, fetched_at)
        print(f"已保存原始 HTML 到本地 raw 目录：{raw_path}")
    elif save_raw and dry_run:
        print("[dry-run] 已请求页面，但不会保存原始 HTML。")

    items = parse_starlink_updates(source, html, http_status, fetched_at, limit)
    print(f"{source['name']} 采集完成：解析得到 {len(items)} 条记录，HTTP 状态码 {http_status}。")
    return items, None


def collect_all_sources(
    source_id: str | None = None,
    limit: int = 20,
    dry_run: bool = False,
    save_raw: bool = False,
    fail_on_error: bool = False,
) -> CollectResult:
    try:
        sources = load_sources()
    except (OSError, ValueError, yaml.YAMLError) as exc:
        message = f"读取来源配置失败：{exc}"
        print(message)
        if fail_on_error:
            raise
        return CollectResult(items=[], sources=[], errors=[message])

    enabled_sources = [source for source in sources if source.get("enabled") is True]
    if source_id:
        enabled_sources = [source for source in enabled_sources if source.get("id") == source_id]

    if not enabled_sources:
        message = f"未找到可采集来源：{source_id or 'enabled sources'}"
        print(message)
        return CollectResult(items=[], sources=[], errors=[message])

    all_items: list[dict[str, Any]] = []
    errors: list[str] = []
    source_names: list[str] = []

    for source in enabled_sources:
        if source.get("id") != "starlink_official_updates":
            print(f"跳过当前阶段未支持的来源：{source.get('id')}")
            continue
        source_names.append(str(source.get("name", source.get("id"))))
        items, error = collect_source(source, limit=limit, save_raw=save_raw, dry_run=dry_run)
        all_items.extend(items)
        if error:
            errors.append(error)
            if fail_on_error:
                break

    all_items = all_items[:limit]
    result = CollectResult(items=all_items, sources=source_names, errors=errors)

    existing_items = {item.get("id"): item for item in load_items() if item.get("id")}
    result.new_count = sum(1 for item in all_items if item.get("id") not in existing_items)
    result.updated_count = sum(1 for item in all_items if item.get("id") in existing_items)
    result.total_items = len(existing_items)

    if dry_run:
        print(f"[dry-run] 本次解析 {len(all_items)} 条记录，不写入 {ITEMS_FILE}。")
        return result

    if all_items:
        new_count, updated_count, total_items = write_items_upsert(all_items)
        result.new_count = new_count
        result.updated_count = updated_count
        result.total_items = total_items
        result.wrote_items = True
        print(f"已更新 {ITEMS_FILE}：新增 {new_count} 条，更新 {updated_count} 条，当前总计 {total_items} 条。")
    else:
        print("本次未采集到有效条目，未更新 data/items.jsonl。")

    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="采集 Starlink 官方 Updates 页面并写入 JSONL。")
    parser.add_argument("--source-id", help="只采集指定来源。")
    parser.add_argument("--limit", type=int, default=20, help="最多输出或写入本次采集记录数，默认 20。")
    parser.add_argument("--dry-run", action="store_true", help="执行采集和解析，但不写入 data/items.jsonl。")
    parser.add_argument("--save-raw", action="store_true", help="保存原始 HTML 到 data/raw/，该目录不提交。")
    parser.add_argument("--fail-on-error", action="store_true", help="采集失败时返回非 0。")
    args = parser.parse_args()

    if args.limit < 1:
        print("--limit 必须是大于等于 1 的整数。")
        return 2

    result = collect_all_sources(
        source_id=args.source_id,
        limit=args.limit,
        dry_run=args.dry_run,
        save_raw=args.save_raw,
        fail_on_error=args.fail_on_error,
    )

    print(
        f"采集汇总：来源 {len(result.sources)} 个，解析 {len(result.items)} 条，"
        f"新增 {result.new_count} 条，更新 {result.updated_count} 条，错误 {len(result.errors)} 个。"
    )

    if result.errors and args.fail_on_error:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
