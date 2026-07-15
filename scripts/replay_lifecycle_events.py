from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit

try:
    from scripts.item_lifecycle import (
        LifecycleUpdatePlan,
        build_lifecycle_update_plan,
        extraction_content_hash,
        semantic_content_hash,
        write_lifecycle_transaction,
    )
    from scripts.operational_health import atomic_write_bundle
except ModuleNotFoundError:
    from item_lifecycle import (
        LifecycleUpdatePlan,
        build_lifecycle_update_plan,
        extraction_content_hash,
        semantic_content_hash,
        write_lifecycle_transaction,
    )
    from operational_health import atomic_write_bundle


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PRODUCTION_DATA_DIR = (PROJECT_ROOT / "data").resolve()
PROTECTED_NAMES = {
    "items.jsonl",
    "item_lifecycle_state.json",
    "item_versions.jsonl",
    "lifecycle_events.jsonl",
}
FIXED_GENERATED_AT = "2026-02-10T00:00:00+00:00"


def _item(raw: dict, source_id: str, source_name: str) -> dict:
    value = {
        **deepcopy(raw),
        "source_id": source_id,
        "source_name": source_name,
        "url": raw["canonical_url"],
        "record_scope": "item",
        "extracted_level": "item_level",
        "published_at": None,
        "modified_at": None,
        "field_evidence": {"title": "fixture_heading"},
        "parser_version": "fixture_parser_v2",
        "source_quality": "medium",
        "extraction_confidence": 0.8,
        "detail_parse_method": "fixture_static",
        "detail_fetch_status": "success",
        "current_run_data_reused": False,
        "first_seen_at": "2026-01-01T00:00:00+00:00",
        "last_seen_at": "2026-01-01T00:00:00+00:00",
        "last_detail_attempt_at": "2026-01-01T00:00:00+00:00",
        "last_detail_success_at": "2026-01-01T00:00:00+00:00",
        "seen_in_current_index": True,
        "starlink_relevance": "fixture",
        "change_status": "unchanged",
        "extraction_change_status": "unchanged",
    }
    value["semantic_content_hash"] = semantic_content_hash(value)
    value["content_hash"] = value["semantic_content_hash"]
    value["extraction_hash"] = extraction_content_hash(value)
    return value


def load_fixture(fixture_dir: Path) -> tuple[dict, dict]:
    payload = json.loads((fixture_dir / "items.json").read_text(encoding="utf-8"))
    if payload.get("source_id") != "fixture_official_updates":
        raise ValueError("replay fixture source_id 必须是虚构来源。")
    records = []
    for raw in payload.get("items", []):
        hostname = (urlsplit(str(raw.get("canonical_url") or "")).hostname or "").lower()
        if not hostname.endswith(".invalid"):
            raise ValueError("replay fixture URL 必须使用 .invalid 域名。")
        records.append(_item(raw, payload["source_id"], payload.get("source_name") or payload["source_id"]))
    if len(records) < 2:
        raise ValueError("replay fixture 至少需要两个虚构条目。")
    return records[0], records[1]


def _observation(complete: bool = True) -> dict[str, dict]:
    return {
        "fixture_official_updates": {
            "index_observation_complete": complete,
            "reachable": complete,
            "checked_at": FIXED_GENERATED_AT,
        }
    }


def _next(plan: LifecycleUpdatePlan, record: dict, run_id: str, observed_at: str, *, complete: bool = True, **policy) -> LifecycleUpdatePlan:
    return build_lifecycle_update_plan(
        plan.updated_items,
        [record],
        _observation(complete),
        lifecycle_state=plan.updated_lifecycle_state,
        existing_versions=plan.all_versions,
        existing_events=plan.all_lifecycle_events,
        run_id=run_id,
        observed_at=observed_at,
        **policy,
    )


def _event_types(plan: LifecycleUpdatePlan) -> list[str]:
    return [str(event.get("event_type")) for event in plan.new_lifecycle_events]


def _result(scenario_id: str, steps: int, expected: list[str], actual: list[str], final_state: str) -> dict:
    if expected != actual:
        raise AssertionError(f"expected={expected}, actual={actual}")
    return {
        "scenario_id": scenario_id,
        "status": "passed",
        "steps": steps,
        "expected_events": expected,
        "actual_events": actual,
        "expected_final_state": final_state,
        "actual_final_state": final_state,
    }


def scenario_initialization(base: dict, _new: dict) -> dict:
    first = build_lifecycle_update_plan([base], [base], _observation(), run_id="init-1", observed_at="2026-01-01T00:00:00+00:00")
    same = _next(first, deepcopy(first.updated_items[0]), "init-1", "2026-01-01T00:00:00+00:00")
    unchanged = _next(first, deepcopy(first.updated_items[0]), "init-2", "2026-01-02T00:00:00+00:00")
    assert len(first.all_versions) == 1 and same.duplicate_run and len(unchanged.new_versions) == 0
    return _result("initialization_idempotency", 3, ["lifecycle_initialized"], _event_types(first), "active")


def scenario_new(_base: dict, new_item: dict) -> dict:
    first = build_lifecycle_update_plan([], [new_item], _observation(), run_id="new-1", observed_at="2026-01-01T00:00:00+00:00")
    second = _next(first, deepcopy(first.updated_items[0]), "new-2", "2026-01-02T00:00:00+00:00")
    assert first.updated_items[0]["change_status"] == "new" and not second.new_lifecycle_events
    return _result("new_then_unchanged", 2, ["item_discovered"], _event_types(first), "active")


def _initialized(base: dict, run_id: str = "base") -> LifecycleUpdatePlan:
    return build_lifecycle_update_plan([base], [base], _observation(), run_id=run_id, observed_at="2026-01-01T00:00:00+00:00")


def scenario_changed(base: dict, _new: dict) -> dict:
    plan = _initialized(base, "changed-base")
    changed = deepcopy(plan.updated_items[0])
    changed["structured_fields"] = {"fixture_status": "gamma"}
    changed = _next(plan, changed, "changed-1", "2026-01-02T00:00:00+00:00")
    repeated = _next(changed, deepcopy(changed.updated_items[0]), "changed-2", "2026-01-03T00:00:00+00:00")
    assert changed.updated_items[0]["semantic_version"] == 2 and not repeated.new_versions
    return _result("semantic_changed_then_unchanged", 3, ["semantic_content_changed"], _event_types(changed), "active")


def scenario_improved(base: dict, _new: dict) -> dict:
    plan = _initialized(base, "improved-base")
    improved = deepcopy(plan.updated_items[0])
    improved["field_evidence"]["summary"] = "fixture_summary_container"
    improved["extraction_confidence"] = 0.9
    changed = _next(plan, improved, "improved-1", "2026-01-02T00:00:00+00:00")
    repeated = _next(changed, deepcopy(changed.updated_items[0]), "improved-2", "2026-01-03T00:00:00+00:00")
    assert changed.updated_items[0]["semantic_version"] == 1 and changed.updated_items[0]["extraction_revision"] == 2 and not repeated.new_versions
    return _result("extraction_improved_then_unchanged", 3, ["extraction_improved"], _event_types(changed), "active")


def scenario_missing_long(base: dict, _new: dict) -> dict:
    plan = _initialized(base, "missing-base")
    seen: list[str] = []
    for index, date in enumerate(("2026-01-08", "2026-01-15", "2026-01-22", "2026-01-29"), 1):
        missing = deepcopy(plan.updated_items[0])
        missing["seen_in_current_index"] = False
        plan = _next(plan, missing, f"missing-{index}", f"{date}T00:00:00+00:00", long_absence_observation_threshold=4, long_absence_min_days=14)
        seen.extend(_event_types(plan))
    assert plan.updated_items[0]["lifecycle_state"] == "long_absent"
    return _result("temporarily_missing_to_long_absent", 5, ["temporarily_missing", "long_absence_reached"], seen, "long_absent")


def scenario_index_failure(base: dict, _new: dict) -> dict:
    plan = _initialized(base, "index-base")
    missing = deepcopy(plan.updated_items[0])
    missing["seen_in_current_index"] = False
    failed = _next(plan, missing, "index-failed", "2026-01-08T00:00:00+00:00", complete=False)
    assert failed.updated_items[0]["consecutive_missing_observations"] == 0
    return _result("index_failure_no_missing", 2, [], _event_types(failed), "active")


def _missing_once(base: dict, prefix: str) -> LifecycleUpdatePlan:
    plan = _initialized(base, f"{prefix}-base")
    missing = deepcopy(plan.updated_items[0])
    missing["seen_in_current_index"] = False
    return _next(plan, missing, f"{prefix}-missing", "2026-01-08T00:00:00+00:00")


def scenario_reappeared(base: dict, _new: dict) -> dict:
    missing = _missing_once(base, "reappear")
    present = deepcopy(missing.updated_items[0])
    present["seen_in_current_index"] = True
    plan = _next(missing, present, "reappear-now", "2026-01-09T00:00:00+00:00")
    return _result("missing_then_reappeared", 3, ["reappeared"], _event_types(plan), "active")


def _failed_three(base: dict, prefix: str) -> LifecycleUpdatePlan:
    plan = _initialized(base, f"{prefix}-base")
    for index in range(1, 4):
        failed = deepcopy(plan.updated_items[0])
        failed.update({"detail_fetch_status": "failed_this_run", "current_run_data_reused": True, "last_detail_error_type": "fixture_timeout"})
        plan = _next(plan, failed, f"{prefix}-fail-{index}", f"2026-01-0{index + 1}T00:00:00+00:00")
    return plan


def scenario_failure_recovery(base: dict, _new: dict) -> dict:
    failed = _failed_three(base, "recover")
    assert failed.updated_items[0]["attention_required"] is True
    recovered = deepcopy(failed.updated_items[0])
    recovered.update({"detail_fetch_status": "success", "current_run_data_reused": False, "last_detail_error_type": None})
    plan = _next(failed, recovered, "recover-now", "2026-01-05T00:00:00+00:00")
    return _result("fetch_failed_three_then_recovered", 5, ["detail_fetch_recovered"], _event_types(plan), "active")


def scenario_reappeared_changed(base: dict, _new: dict) -> dict:
    missing = _missing_once(base, "reappear-change")
    present = deepcopy(missing.updated_items[0])
    present["seen_in_current_index"] = True
    present["structured_fields"] = {"fixture_status": "changed"}
    plan = _next(missing, present, "reappear-change-now", "2026-01-09T00:00:00+00:00")
    return _result("reappeared_and_changed", 3, ["reappeared", "semantic_content_changed"], _event_types(plan), "active")


def scenario_recovered_changed(base: dict, _new: dict) -> dict:
    failed = _failed_three(base, "recover-change")
    recovered = deepcopy(failed.updated_items[0])
    recovered.update({"detail_fetch_status": "success", "current_run_data_reused": False, "last_detail_error_type": None, "structured_fields": {"fixture_status": "changed"}})
    plan = _next(failed, recovered, "recover-change-now", "2026-01-05T00:00:00+00:00")
    return _result("recovered_and_changed", 5, ["detail_fetch_recovered", "semantic_content_changed"], _event_types(plan), "active")


def scenario_parser_change(base: dict, _new: dict) -> dict:
    plan = _initialized(base, "parser-base")
    current = deepcopy(plan.updated_items[0])
    current["parser_version"] = "fixture_parser_v3"
    changed = _next(plan, current, "parser-change", "2026-01-02T00:00:00+00:00")
    assert changed.updated_items[0]["change_status"] == "unchanged" and changed.updated_items[0]["extraction_change_status"] == "unchanged"
    return _result("parser_version_only", 2, [], _event_types(changed), "active")


def scenario_stale(base: dict, _new: dict) -> dict:
    plan = build_lifecycle_update_plan([base], [base], _observation(), run_id="run-new", observed_at="2026-02-10T00:00:00+00:00")
    stale_item = deepcopy(plan.updated_items[0])
    stale_item["structured_fields"] = {"fixture_status": "old"}
    stale = _next(plan, stale_item, "run-old", "2026-02-01T00:00:00+00:00")
    assert stale.ignored_as_stale and stale.updated_items == plan.updated_items
    return _result("stale_run_ignored", 2, [], _event_types(stale), "active")


def scenario_transaction(base: dict, _new: dict) -> dict:
    plan = _initialized(base, "transaction-base")
    with tempfile.TemporaryDirectory(prefix="phase4d-replay-") as directory:
        root = Path(directory)
        paths = {
            "items_path": root / "items.jsonl",
            "lifecycle_state_path": root / "state.json",
            "versions_path": root / "versions.jsonl",
            "events_path": root / "events.jsonl",
            "report_path": root / "report.json",
        }
        write_lifecycle_transaction(plan, **paths)
        before = {name: path.read_bytes() for name, path in paths.items()}
        changed_item = deepcopy(plan.updated_items[0])
        changed_item["structured_fields"] = {"fixture_status": "transaction-change"}
        changed = _next(plan, changed_item, "transaction-change", "2026-01-02T00:00:00+00:00")
        real_replace = os.replace
        failed = False

        def flaky_replace(source, destination):
            nonlocal failed
            if not failed and Path(destination) == paths["versions_path"]:
                failed = True
                raise OSError("synthetic transaction failure")
            return real_replace(source, destination)

        try:
            lifecycle_module = sys.modules[write_lifecycle_transaction.__module__]
            with patch.object(lifecycle_module.os, "replace", side_effect=flaky_replace):
                write_lifecycle_transaction(changed, **paths)
        except OSError:
            pass
        else:
            raise AssertionError("synthetic transaction failure was not raised")
        assert before == {name: path.read_bytes() for name, path in paths.items()}
    return _result("transaction_failure_rollback", 2, [], [], "active")


SCENARIOS = {
    "initialization_idempotency": scenario_initialization,
    "new_then_unchanged": scenario_new,
    "semantic_changed_then_unchanged": scenario_changed,
    "extraction_improved_then_unchanged": scenario_improved,
    "temporarily_missing_to_long_absent": scenario_missing_long,
    "index_failure_no_missing": scenario_index_failure,
    "missing_then_reappeared": scenario_reappeared,
    "fetch_failed_three_then_recovered": scenario_failure_recovery,
    "reappeared_and_changed": scenario_reappeared_changed,
    "recovered_and_changed": scenario_recovered_changed,
    "parser_version_only": scenario_parser_change,
    "stale_run_ignored": scenario_stale,
    "transaction_failure_rollback": scenario_transaction,
}


def run_replay(fixture_dir: Path, scenario_ids: list[str] | None = None) -> dict:
    base, new_item = load_fixture(fixture_dir)
    selected = scenario_ids or list(SCENARIOS)
    results = []
    for scenario_id in selected:
        if scenario_id not in SCENARIOS:
            results.append({"scenario_id": scenario_id, "status": "failed", "reason": "unknown_scenario"})
            continue
        try:
            results.append(SCENARIOS[scenario_id](deepcopy(base), deepcopy(new_item)))
        except Exception as exc:
            results.append({"scenario_id": scenario_id, "status": "failed", "reason": type(exc).__name__})
    passed = sum(result.get("status") == "passed" for result in results)
    return {
        "version": 1,
        "generated_at": FIXED_GENERATED_AT,
        "stage": "4D",
        "mode": "synthetic_offline_replay",
        "fixture_domain": "example.invalid",
        "scenario_count": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "network_accessed": False,
        "production_files_modified": False,
        "scenarios": results,
    }


def _inside(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="完全离线回放 Phase 4D 生命周期事件。")
    parser.add_argument("--scenario", action="append")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--fixture-dir", default=str(PROJECT_ROOT / "tests" / "fixtures" / "lifecycle_replay"))
    parser.add_argument("--output-dir")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--no-write", action="store_true")
    parser.add_argument("--write-report")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    if args.output_dir and _inside(Path(args.output_dir), PRODUCTION_DATA_DIR):
        print("安全错误：replay output-dir 不得指向项目 data/ 生产目录。")
        return 2
    report_path = Path(args.write_report).resolve() if args.write_report else None
    if report_path and report_path.name in PROTECTED_NAMES:
        print("安全错误：replay 不得覆盖生产生命周期状态文件。")
        return 2
    selected = None if args.all or not args.scenario else args.scenario
    if args.output_dir:
        Path(args.output_dir).mkdir(parents=True, exist_ok=True)
    report = run_replay(Path(args.fixture_dir), selected)
    if report_path and not args.no_write:
        atomic_write_bundle({report_path: json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"})
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"离线回放：{report['passed']}/{report['scenario_count']} passed")
        print("network_accessed=false")
        print("production_files_modified=false")
        if args.no_write:
            print("[no-write] 未写入 replay 报告。")
    return 1 if args.strict and report["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
