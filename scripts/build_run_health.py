from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

try:
    from scripts.operational_health import (
        ALERT_REPORT_FILE,
        RUN_HEALTH_HISTORY_FILE,
        build_run_health_data,
        load_json,
        load_jsonl,
        now_iso,
        policy_from_env,
        write_health_evaluation,
    )
except ModuleNotFoundError:
    from operational_health import (
        ALERT_REPORT_FILE,
        RUN_HEALTH_HISTORY_FILE,
        build_run_health_data,
        load_json,
        load_jsonl,
        now_iso,
        policy_from_env,
        write_health_evaluation,
    )


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"


def main() -> int:
    parser = argparse.ArgumentParser(description="构建 Phase 4D 运行健康报告。")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--no-write", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    lifecycle = load_json(DATA_DIR / "lifecycle_report.json", {})
    started_at = os.getenv("RUN_STARTED_AT") or lifecycle.get("generated_at") or now_iso()
    context = {
        "run_id": os.getenv("RUN_ID") or lifecycle.get("run_id") or f"health-{started_at}",
        "started_at": started_at,
        "finished_at": os.getenv("RUN_FINISHED_AT") or now_iso(),
        "output_check_status": os.getenv("OUTPUT_CHECK_STATUS") or "unknown",
        "project_audit_status": os.getenv("PROJECT_AUDIT_STATUS") or "unknown",
        "email_status": os.getenv("EMAIL_STATUS") or "unknown",
        "gitee_status": os.getenv("GITEE_SYNC_STATUS") or "unknown",
    }
    policy, warnings = policy_from_env()
    evaluation = build_run_health_data(
        source_status=load_json(DATA_DIR / "source_status.json", {}),
        item_extraction_report=load_json(DATA_DIR / "item_extraction_report.json", {}),
        lifecycle_report=lifecycle,
        llm_audit=load_json(DATA_DIR / "llm_audit.json", {}),
        alert_report=load_json(ALERT_REPORT_FILE, {}),
        run_context=context,
        previous_history=load_jsonl(RUN_HEALTH_HISTORY_FILE),
        policy=policy,
    )
    evaluation.health.setdefault("warnings", []).extend(warnings)
    if not args.no_write:
        write_health_evaluation(evaluation)
    if args.json:
        print(json.dumps(evaluation.health, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"整体运行健康：{evaluation.health.get('overall_health', 'unknown')}")
        for name, component in evaluation.health.get("components", {}).items():
            print(f"{name}: {component.get('status', 'unknown')}")
        if args.no_write:
            print("[no-write] 未写入运行健康文件。")
    return 1 if args.strict and (not evaluation.write_allowed or evaluation.health.get("overall_health") == "unhealthy") else 0


if __name__ == "__main__":
    sys.exit(main())
