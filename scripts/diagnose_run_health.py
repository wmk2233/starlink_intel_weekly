from __future__ import annotations

import argparse
import json
import sys

try:
    from scripts.operational_health import RUN_HEALTH_FILE, RUN_HEALTH_HISTORY_FILE, load_json, load_jsonl
except ModuleNotFoundError:
    from operational_health import RUN_HEALTH_FILE, RUN_HEALTH_HISTORY_FILE, load_json, load_jsonl


def main() -> int:
    parser = argparse.ArgumentParser(description="只读诊断 Phase 4D 运行健康。")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--history", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args()
    health = load_json(RUN_HEALTH_FILE, {})
    payload = {
        "stage": "4D",
        "run_id": health.get("run_id"),
        "overall_health": health.get("overall_health", "unknown"),
        "duration_seconds": health.get("duration_seconds"),
        "components": {key: {"status": value.get("status", "unknown")} for key, value in health.get("components", {}).items()},
        "alert_summary": health.get("alert_summary", {}),
    }
    if args.history:
        payload["history"] = load_jsonl(RUN_HEALTH_HISTORY_FILE)[-20:]
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"整体运行健康：{payload['overall_health']}")
        for name, component in payload["components"].items():
            print(f"{name}: {component['status']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
