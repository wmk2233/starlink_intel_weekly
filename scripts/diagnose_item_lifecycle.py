from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from item_lifecycle import (
    ITEM_LIFECYCLE_STATE_FILE,
    ITEM_VERSIONS_FILE,
    LIFECYCLE_EVENTS_FILE,
    load_jsonl,
    load_lifecycle_state,
)


def _matches(value: dict[str, Any], source_id: str | None, record_id: str | None) -> bool:
    if source_id and value.get("source_id") != source_id:
        return False
    if record_id and value.get("record_id") != record_id:
        return False
    return True


def _state_rows(source_id: str | None, record_id: str | None, attention_only: bool) -> list[dict[str, Any]]:
    state = load_lifecycle_state(ITEM_LIFECYCLE_STATE_FILE)
    rows: list[dict[str, Any]] = []
    for value in state.get("items", {}).values():
        if not isinstance(value, dict) or not _matches(value, source_id, record_id):
            continue
        if attention_only and value.get("attention_required") is not True:
            continue
        rows.append(
            {
                "record_id": value.get("record_id"),
                "source_id": value.get("source_id"),
                "canonical_url": value.get("canonical_url"),
                "lifecycle_state": value.get("lifecycle_state"),
                "change_status": value.get("change_status"),
                "extraction_change_status": value.get("extraction_change_status"),
                "semantic_version": value.get("semantic_version"),
                "extraction_revision": value.get("extraction_revision"),
                "consecutive_missing_observations": value.get("consecutive_missing_observations"),
                "consecutive_detail_failures": value.get("consecutive_detail_failures"),
                "last_event_type": value.get("last_lifecycle_event"),
                "attention_required": value.get("attention_required"),
            }
        )
    return rows


def _history_rows(path: Path, source_id: str | None, record_id: str | None, kind: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for value in load_jsonl(path):
        if not _matches(value, source_id, record_id):
            continue
        if kind == "events":
            rows.append(
                {
                    key: value.get(key)
                    for key in (
                        "event_id",
                        "run_id",
                        "occurred_at",
                        "event_type",
                        "record_id",
                        "source_id",
                        "canonical_url",
                        "previous_lifecycle_state",
                        "current_lifecycle_state",
                        "changed_fields",
                        "attention_required",
                    )
                }
            )
        else:
            rows.append(
                {
                    key: value.get(key)
                    for key in (
                        "version_id",
                        "run_id",
                        "observed_at",
                        "version_kind",
                        "record_id",
                        "source_id",
                        "canonical_url",
                        "semantic_version",
                        "extraction_revision",
                        "changed_fields",
                    )
                }
            )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="只读查看阶段 4C item 生命周期状态。")
    parser.add_argument("--all", action="store_true", help="同时显示状态、事件和版本。")
    parser.add_argument("--source-id")
    parser.add_argument("--record-id")
    parser.add_argument("--events", action="store_true")
    parser.add_argument("--versions", action="store_true")
    parser.add_argument("--attention-only", action="store_true")
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--no-write", action="store_true", help="兼容显式只读调用；脚本始终不写文件。")
    args = parser.parse_args()

    include_state = args.all or not (args.events or args.versions)
    payload: dict[str, Any] = {"mode": "read_only", "stage": "4C"}
    if include_state:
        payload["items"] = _state_rows(args.source_id, args.record_id, args.attention_only)
    if args.all or args.events:
        payload["events"] = _history_rows(LIFECYCLE_EVENTS_FILE, args.source_id, args.record_id, "events")
    if args.all or args.versions:
        payload["versions"] = _history_rows(ITEM_VERSIONS_FILE, args.source_id, args.record_id, "versions")

    if args.as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("阶段 4C 条目生命周期诊断（只读）")
        for section in ("items", "events", "versions"):
            if section not in payload:
                continue
            print(f"{section}: {len(payload[section])}")
            for row in payload[section]:
                print(" | ".join(f"{key}={value}" for key, value in row.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
