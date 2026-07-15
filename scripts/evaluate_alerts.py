from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    from scripts.operational_health import (
        ALERT_EVENTS_FILE,
        ALERT_REPORT_FILE,
        ALERT_STATE_FILE,
        RUN_HEALTH_HISTORY_FILE,
        default_alert_state,
        evaluate_alerts_data,
        load_json,
        load_jsonl,
        now_iso,
        policy_from_env,
        write_alert_evaluation,
    )
except ModuleNotFoundError:
    from operational_health import (
        ALERT_EVENTS_FILE,
        ALERT_REPORT_FILE,
        ALERT_STATE_FILE,
        RUN_HEALTH_HISTORY_FILE,
        default_alert_state,
        evaluate_alerts_data,
        load_json,
        load_jsonl,
        now_iso,
        policy_from_env,
        write_alert_evaluation,
    )


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"


def main() -> int:
    parser = argparse.ArgumentParser(description="离线评估 Phase 4D 运维告警。")
    parser.add_argument("--lifecycle-report", default=str(DATA_DIR / "lifecycle_report.json"))
    parser.add_argument("--source-status", default=str(DATA_DIR / "source_status.json"))
    parser.add_argument("--item-extraction-report", default=str(DATA_DIR / "item_extraction_report.json"))
    parser.add_argument("--llm-audit", default=str(DATA_DIR / "llm_audit.json"))
    parser.add_argument("--run-context", help="只含有限运行状态的 JSON 文件。")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--no-write", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    lifecycle_report = load_json(Path(args.lifecycle_report), {})
    lifecycle_state = load_json(DATA_DIR / "item_lifecycle_state.json", {})
    lifecycle_events = load_jsonl(DATA_DIR / "lifecycle_events.jsonl")
    run_context = load_json(Path(args.run_context), {}) if args.run_context else {}
    run_context.setdefault("run_id", lifecycle_report.get("run_id") or f"alert-{now_iso()}")
    run_context.setdefault("started_at", lifecycle_report.get("generated_at") or now_iso())
    policy, config_warnings = policy_from_env()
    evaluation = evaluate_alerts_data(
        lifecycle_events=lifecycle_events,
        lifecycle_state=lifecycle_state,
        lifecycle_report=lifecycle_report,
        source_status=load_json(Path(args.source_status), {}),
        item_extraction_report=load_json(Path(args.item_extraction_report), {}),
        llm_audit=load_json(Path(args.llm_audit), {}),
        run_context=run_context,
        previous_state=load_json(ALERT_STATE_FILE, default_alert_state()),
        existing_alert_events=load_jsonl(ALERT_EVENTS_FILE),
        health_history=load_jsonl(RUN_HEALTH_HISTORY_FILE),
        policy=policy,
    )
    evaluation.report.setdefault("warnings", []).extend(config_warnings)
    if not args.no_write:
        write_alert_evaluation(evaluation)
    if args.json:
        print(json.dumps(evaluation.report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"整体告警状态：{evaluation.report.get('overall_alert_status', 'unknown')}")
        print(f"本轮告警：{len(evaluation.new_events)}")
        print(f"当前 open conditions：{len(evaluation.state.get('open_conditions', {}))}")
        if args.no_write:
            print("[no-write] 未写入告警状态文件。")
    if args.strict and (not evaluation.write_allowed or evaluation.report.get("overall_alert_status") == "critical"):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
