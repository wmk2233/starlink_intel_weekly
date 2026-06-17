from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass, field
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
SOURCE_STATUS_FILE = PROJECT_ROOT / "data" / "source_status.json"
RAW_DIR = PROJECT_ROOT / "data" / "raw"
USER_AGENT = "Mozilla/5.0 starlink-intel-weekly/0.2"
COLLECTOR_NAME = "rule_based_html_v2"


@dataclass
class SourceFetch:
    source: dict[str, Any]
    fetched_at: str
    http_status: int | None
    reachable: bool
    html: str = ""
    page_hash: str | None = None
    page_text: str = ""
    error: str | None = None


@dataclass
class CollectResult:
    items: list[dict[str, Any]]
    sources: list[str]
    errors: list[str]
    source_statuses: dict[str, dict[str, Any]] = field(default_factory=dict)
    new_count: int = 0
    changed_count: int = 0
    unchanged_count: int = 0
    total_items: int = 0
    wrote_items: bool = False
    wrote_status: bool = False

    @property
    def page_change_status(self) -> str:
        if not self.source_statuses:
            return "unknown"
        return next(iter(self.source_statuses.values())).get("change_status", "unknown")

    @property
    def health_status(self) -> str:
        if not self.source_statuses:
            return "unknown"
        return next(iter(self.source_statuses.values())).get("health_status", "unknown")


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def normalize_text(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", value).strip()


def compute_hash(value: str | None) -> str:
    normalized = normalize_text(value)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


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


def load_source_status(path: Path = SOURCE_STATUS_FILE) -> dict[str, Any]:
    if not path.exists():
        return {"generated_at": None, "sources": {}}

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        print(f"来源状态文件无法解析，将重新生成：{path}")
        return {"generated_at": None, "sources": {}}

    if not isinstance(data, dict):
        return {"generated_at": None, "sources": {}}
    sources = data.get("sources")
    if not isinstance(sources, dict):
        data["sources"] = {}
    return data


def write_source_status(status: dict[str, Any], path: Path = SOURCE_STATUS_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    status["generated_at"] = now_iso()
    path.write_text(json.dumps(status, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def make_item_id(url: str, title: str) -> str:
    return compute_hash(f"{url}|{title}")


def item_content_hash(item: dict[str, Any]) -> str:
    return compute_hash(
        " ".join(
            [
                str(item.get("title") or ""),
                str(item.get("url") or ""),
                str(item.get("summary") or ""),
                str(item.get("evidence") or ""),
            ]
        )
    )


def normalize_url(href: str, base_url: str) -> str | None:
    if not href:
        return None

    absolute = urljoin(base_url, href.strip())
    absolute, _fragment = urldefrag(absolute)
    parts = urlsplit(absolute)
    if parts.scheme not in {"http", "https"}:
        return None

    return urlunsplit((parts.scheme, parts.netloc, parts.path.rstrip("/") or "/", "", ""))


def is_updates_url(url: str) -> bool:
    parts = urlsplit(url)
    return parts.netloc.lower().endswith("starlink.com") and "/updates" in parts.path.lower()


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
    return normalize_text(heading.get_text(" ")) if heading else ""


def soup_main_text(soup: BeautifulSoup) -> str:
    for unwanted in soup(["script", "style", "noscript", "svg"]):
        unwanted.decompose()
    main = soup.find("main")
    if main:
        return normalize_text(main.get_text(" "))
    return normalize_text(soup.get_text(" "))


def page_excerpt(page_text: str, max_length: int = 500) -> str:
    return normalize_text(page_text)[:max_length].strip()


def page_title(soup: BeautifulSoup) -> str:
    if soup.title and soup.title.string:
        return normalize_text(soup.title.string)
    h1 = soup.find("h1")
    if h1:
        return normalize_text(h1.get_text(" "))
    return "Starlink Official Updates"


def fetch_source(source: dict[str, Any], timeout: int = 20) -> SourceFetch:
    fetched_at = now_iso()
    try:
        response = requests.get(
            source["url"],
            headers={"User-Agent": USER_AGENT},
            timeout=timeout,
        )
        http_status = response.status_code
        response.raise_for_status()
    except requests.RequestException as exc:
        return SourceFetch(
            source=source,
            fetched_at=fetched_at,
            http_status=getattr(getattr(exc, "response", None), "status_code", None),
            reachable=False,
            error=f"采集失败：{exc.__class__.__name__}",
        )

    soup = BeautifulSoup(response.text, "html.parser")
    text = soup_main_text(soup)
    hash_base = text or normalize_text(response.text)
    return SourceFetch(
        source=source,
        fetched_at=fetched_at,
        http_status=http_status,
        reachable=True,
        html=response.text,
        page_hash=compute_hash(hash_base),
        page_text=text,
    )


def build_item(
    source: dict[str, Any],
    title: str,
    url: str,
    fetched_at: str,
    http_status: int | None,
    summary: str,
    evidence: str,
) -> dict[str, Any]:
    item = {
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
    item["content_hash"] = item_content_hash(item)
    return item


def extract_items_from_starlink_updates(fetch: SourceFetch, limit: int) -> list[dict[str, Any]]:
    source = fetch.source
    soup = BeautifulSoup(fetch.html, "html.parser")
    title = page_title(soup)
    excerpt = page_excerpt(fetch.page_text)

    items_by_id: dict[str, dict[str, Any]] = {}
    for link in soup.find_all("a", href=True):
        normalized = normalize_url(link.get("href", ""), source["url"])
        if not normalized or not is_updates_url(normalized):
            continue

        link_text = normalize_text(link.get_text(" "))
        title_candidate = link_text or nearby_heading(link) or title_from_slug(normalized)
        evidence = normalize_text(link_text or nearby_heading(link) or excerpt)
        summary = f"规则化采集发现 Starlink 官方 Updates 相关链接：{title_candidate}"
        item = build_item(
            source=source,
            title=title_candidate,
            url=normalized,
            fetched_at=fetch.fetched_at,
            http_status=fetch.http_status,
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
            fetched_at=fetch.fetched_at,
            http_status=fetch.http_status,
            summary=summary,
            evidence=excerpt[:500],
        )
        items_by_id[item["id"]] = item

    return list(items_by_id.values())[:limit]


def apply_item_change_metadata(
    items: list[dict[str, Any]],
    existing_by_id: dict[str, dict[str, Any]],
    fetched_at: str,
) -> tuple[int, int, int]:
    new_count = 0
    changed_count = 0
    unchanged_count = 0

    for item in items:
        item_id = item.get("id")
        existing = existing_by_id.get(item_id)
        current_hash = item.get("content_hash") or item_content_hash(item)
        item["content_hash"] = current_hash
        item["last_seen_at"] = fetched_at

        if not existing:
            item["first_seen_at"] = fetched_at
            item["last_changed_at"] = fetched_at
            item["change_status"] = "new"
            item["previous_content_hash"] = None
            new_count += 1
            continue

        previous_hash = existing.get("content_hash")
        item["first_seen_at"] = existing.get("first_seen_at") or existing.get("fetched_at") or fetched_at
        item["previous_content_hash"] = previous_hash
        if previous_hash == current_hash:
            item["last_changed_at"] = existing.get("last_changed_at") or item["first_seen_at"]
            item["change_status"] = "unchanged"
            unchanged_count += 1
        else:
            item["last_changed_at"] = fetched_at
            item["change_status"] = "changed"
            changed_count += 1

    return new_count, changed_count, unchanged_count


def write_items_upsert(new_items: list[dict[str, Any]], path: Path = ITEMS_FILE) -> tuple[int, int, int, int]:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing_items = load_items(path)
    by_id = {item.get("id"): item for item in existing_items if item.get("id")}

    fetched_at = new_items[0].get("last_seen_at") or new_items[0].get("fetched_at") if new_items else now_iso()
    new_count, changed_count, unchanged_count = apply_item_change_metadata(new_items, by_id, str(fetched_at))

    for item in new_items:
        item_id = item.get("id")
        if not item_id:
            continue
        merged = dict(by_id.get(item_id, {}))
        merged.update(item)
        by_id[item_id] = merged

    ordered = sorted(
        by_id.values(),
        key=lambda item: str(item.get("last_seen_at") or item.get("fetched_at") or ""),
        reverse=True,
    )
    with path.open("w", encoding="utf-8", newline="\n") as file:
        for item in ordered:
            file.write(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n")

    return new_count, changed_count, unchanged_count, len(ordered)


def update_source_status(
    status: dict[str, Any],
    fetch: SourceFetch,
    items: list[dict[str, Any]],
    new_count: int,
    changed_count: int,
    unchanged_count: int,
) -> dict[str, Any]:
    sources = status.setdefault("sources", {})
    source = fetch.source
    source_id = source["id"]
    previous = sources.get(source_id, {})
    previous_page_hash = previous.get("current_page_hash")

    if not fetch.reachable:
        change_status = "failed"
        last_changed_at = previous.get("last_changed_at")
    elif not previous_page_hash:
        change_status = "new"
        last_changed_at = fetch.fetched_at
    elif previous_page_hash != fetch.page_hash:
        change_status = "changed"
        last_changed_at = fetch.fetched_at
    else:
        change_status = "unchanged"
        last_changed_at = previous.get("last_changed_at") or fetch.fetched_at

    source_status = {
        "source_id": source_id,
        "source_name": source.get("name"),
        "url": source.get("url"),
        "source_type": source.get("source_type"),
        "reliability_tier": source.get("reliability_tier"),
        "last_checked_at": fetch.fetched_at,
        "http_status": fetch.http_status,
        "reachable": fetch.reachable,
        "health_status": "reachable" if fetch.reachable else "failed",
        "change_status": change_status,
        "current_page_hash": fetch.page_hash,
        "previous_page_hash": previous_page_hash,
        "last_changed_at": last_changed_at,
        "items_collected": len(items),
        "new_items": new_count,
        "changed_items": changed_count,
        "unchanged_items": unchanged_count,
        "error": fetch.error,
        "collector": COLLECTOR_NAME,
    }
    sources[source_id] = source_status
    return source_status


def write_failed_source_status(status: dict[str, Any], fetch: SourceFetch) -> dict[str, Any]:
    return update_source_status(status, fetch, [], 0, 0, 0)


def save_raw_html(source_id: str, html: str, fetched_at: str) -> Path:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    safe_time = re.sub(r"[^0-9A-Za-z_-]+", "-", fetched_at)
    path = RAW_DIR / f"{source_id}-{safe_time}.html"
    path.write_text(html, encoding="utf-8", newline="\n")
    return path


def collect_source(
    source: dict[str, Any],
    existing_items: dict[str, dict[str, Any]],
    source_status: dict[str, Any],
    limit: int = 20,
    save_raw: bool = False,
    dry_run: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, Any], str | None]:
    fetch = fetch_source(source)
    if not fetch.reachable:
        status = write_failed_source_status(source_status, fetch)
        message = f"{source.get('name', source.get('id'))} 采集失败：{fetch.error}"
        print(message)
        return [], status, message

    if save_raw and not dry_run:
        raw_path = save_raw_html(source["id"], fetch.html, fetch.fetched_at)
        print(f"已保存原始 HTML 到本地 raw 目录：{raw_path}")
    elif save_raw and dry_run:
        print("[dry-run] 已请求页面，但不会保存原始 HTML。")

    items = extract_items_from_starlink_updates(fetch, limit)
    new_count, changed_count, unchanged_count = apply_item_change_metadata(items, existing_items, fetch.fetched_at)
    status = update_source_status(source_status, fetch, items, new_count, changed_count, unchanged_count)
    print_source_summary(status)
    return items, status, None


def print_source_summary(status: dict[str, Any]) -> None:
    print(f"来源：{status.get('source_name')}")
    print(f"HTTP 状态：{status.get('http_status')}")
    print(f"页面状态：{status.get('health_status')}")
    print(f"页面变化状态：{status.get('change_status')}")
    print(f"采集条目数：{status.get('items_collected')}")
    print(f"新增条目数：{status.get('new_items')}")
    print(f"变化条目数：{status.get('changed_items')}")
    print(f"未变化条目数：{status.get('unchanged_items')}")


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

    existing_items = {item.get("id"): item for item in load_items() if item.get("id")}
    source_status = load_source_status()
    all_items: list[dict[str, Any]] = []
    errors: list[str] = []
    source_names: list[str] = []
    source_statuses: dict[str, dict[str, Any]] = {}

    for source in enabled_sources:
        if source.get("id") != "starlink_official_updates":
            print(f"跳过当前阶段未支持的来源：{source.get('id')}")
            continue
        source_names.append(str(source.get("name", source.get("id"))))
        items, status, error = collect_source(
            source,
            existing_items=existing_items,
            source_status=source_status,
            limit=limit,
            save_raw=save_raw,
            dry_run=dry_run,
        )
        source_statuses[source["id"]] = status
        all_items.extend(items)
        if error:
            errors.append(error)
            if fail_on_error:
                break

    all_items = all_items[:limit]
    result = CollectResult(items=all_items, sources=source_names, errors=errors, source_statuses=source_statuses)
    result.new_count = sum(1 for item in all_items if item.get("change_status") == "new")
    result.changed_count = sum(1 for item in all_items if item.get("change_status") == "changed")
    result.unchanged_count = sum(1 for item in all_items if item.get("change_status") == "unchanged")
    result.total_items = len(existing_items)

    if dry_run:
        print(f"[dry-run] 本次解析 {len(all_items)} 条记录，不写入 {ITEMS_FILE}。")
        print(f"[dry-run] 不写入 {SOURCE_STATUS_FILE}。")
        return result

    if all_items:
        new_count, changed_count, unchanged_count, total_items = write_items_upsert(all_items)
        result.new_count = new_count
        result.changed_count = changed_count
        result.unchanged_count = unchanged_count
        result.total_items = total_items
        result.wrote_items = True
        print(f"{ITEMS_FILE} 已更新：新增 {new_count} 条，变化 {changed_count} 条，未变化 {unchanged_count} 条，当前总计 {total_items} 条。")
    else:
        print("本次未采集到有效条目，未更新 data/items.jsonl。")

    write_source_status(source_status)
    result.wrote_status = True
    print(f"{SOURCE_STATUS_FILE} 已更新。")
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
        f"新增 {result.new_count} 条，变化 {result.changed_count} 条，未变化 {result.unchanged_count} 条，错误 {len(result.errors)} 个。"
    )

    if result.errors and args.fail_on_error:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
