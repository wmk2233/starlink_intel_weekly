from __future__ import annotations

import argparse
import json
import sys

try:
    from scripts.operational_health import ALERT_EVENTS_FILE, ALERT_STATE_FILE, default_alert_state, load_json, load_jsonl
except ModuleNotFoundError:
    from operational_health import ALERT_EVENTS_FILE, ALERT_STATE_FILE, default_alert_state, load_json, load_jsonl


ALLOWED_FIELDS = (
    "alert_key", "alert_type", "severity", "status", "source_id", "record_id",
    "first_opened_at", "last_observed_at", "consecutive_observations", "cooldown_until", "message_code",
)


def limited(value: dict) -> dict:
    return {key: value.get(key) for key in ALLOWED_FIELDS}


def main() -> int:
    parser = argparse.ArgumentParser(description="只读诊断 Phase 4D 告警。")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--open-only", action="store_true")
    parser.add_argument("--severity")
    parser.add_argument("--source-id")
    parser.add_argument("--record-id")
    parser.add_argument("--history", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args()
    state = load_json(ALERT_STATE_FILE, default_alert_state())
    rows = list(state.get("open_conditions", {}).values())
    if args.history:
        rows.extend(load_jsonl(ALERT_EVENTS_FILE))
    selected = []
    for row in rows:
        if args.severity and row.get("severity") != args.severity:
            continue
        if args.source_id and row.get("source_id") != args.source_id:
            continue
        if args.record_id and row.get("record_id") != args.record_id:
            continue
        if args.open_only and row.get("status", "open") != "open":
            continue
        selected.append(limited(row))
    if args.json:
        print(json.dumps({"stage": "4D", "count": len(selected), "alerts": selected}, ensure_ascii=False, indent=2))
    else:
        print(f"告警记录：{len(selected)}")
        for row in selected:
            print(" | ".join(str(row.get(key) or "-") for key in ("alert_type", "severity", "status", "source_id", "record_id")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
