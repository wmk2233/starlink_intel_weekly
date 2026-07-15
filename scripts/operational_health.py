from __future__ import annotations

import hashlib
import json
import os
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import median
from typing import Any, Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
ALERT_STATE_FILE = DATA_DIR / "alert_state.json"
ALERT_EVENTS_FILE = DATA_DIR / "alert_events.jsonl"
ALERT_REPORT_FILE = DATA_DIR / "alert_report.json"
RUN_HEALTH_FILE = DATA_DIR / "run_health.json"
RUN_HEALTH_HISTORY_FILE = DATA_DIR / "run_health_history.jsonl"

DEFAULT_ALERT_COOLDOWN_HOURS = 24
DEFAULT_MAX_ALERT_EVENTS = 2000
DEFAULT_MAX_PROCESSED_ALERT_EVENT_IDS = 2000
DEFAULT_MAX_RUN_HEALTH_RECORDS = 400
DEFAULT_CANDIDATE_TREND_WINDOW = 8
DEFAULT_CANDIDATE_COLLAPSE_RATIO = 0.25
DEFAULT_CANDIDATE_COLLAPSE_CONSECUTIVE_RUNS = 2
DEFAULT_DETAIL_SUCCESS_RATE_WARNING_THRESHOLD = 0.5
DEFAULT_DETAIL_SUCCESS_RATE_CONSECUTIVE_RUNS = 2
DEFAULT_SOURCE_UNREACHABLE_HIGH_THRESHOLD = 2
DEFAULT_LLM_VALIDATION_HIGH_THRESHOLD = 3
DEFAULT_RUNTIME_WARNING_SECONDS = 900

ALERT_SEVERITIES = ("info", "warning", "high", "critical")
ALERT_ACTIONS = ("notify", "open", "update", "escalate", "resolve", "suppress")
SEVERITY_RANK = {name: index for index, name in enumerate(ALERT_SEVERITIES)}
EVENT_NOTIFICATION_RULES = {
    "item_discovered": ("info", "collection"),
    "semantic_content_changed": ("warning", "content_review"),
    "extraction_improved": ("info", "extraction"),
    "detail_fetch_recovered": ("info", "collection"),
    "reappeared": ("info", "collection"),
}
INTEGRITY_ALERT_TYPES = {
    "output_validation_failed",
    "project_audit_failed",
    "state_integrity_failed",
    "transaction_failed",
    "stable_id_collision",
}
SEVERITY_SAFETY_NOTE = (
    "告警等级只表示自动化系统中的人工复查优先级，不表示 Starlink、SpaceX 或相关事件的"
    "战略重要性、影响程度或安全等级。"
)


@dataclass
class AlertEvaluation:
    state: dict[str, Any]
    all_events: list[dict[str, Any]]
    report: dict[str, Any]
    new_events: list[dict[str, Any]]
    warnings: list[str] = field(default_factory=list)
    write_allowed: bool = True


@dataclass
class HealthEvaluation:
    health: dict[str, Any]
    history: list[dict[str, Any]]
    write_allowed: bool = True
    warnings: list[str] = field(default_factory=list)


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def parse_datetime(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed


def safe_positive_int(value: object, default: int, name: str, warnings: list[str] | None = None) -> int:
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError):
        parsed = default
    if parsed < 1:
        parsed = default
    if warnings is not None and value not in (None, "") and str(parsed) != str(value).strip():
        warnings.append(f"{name} 配置无效，已使用安全默认值 {default}。")
    return parsed


def safe_ratio(value: object, default: float, name: str, warnings: list[str] | None = None) -> float:
    try:
        parsed = float(str(value).strip())
    except (TypeError, ValueError):
        parsed = default
    if not 0 < parsed <= 1:
        parsed = default
    if warnings is not None and value not in (None, ""):
        try:
            original = float(str(value).strip())
        except ValueError:
            original = None
        if original != parsed:
            warnings.append(f"{name} 配置无效，已使用安全默认值 {default}。")
    return parsed


def policy_from_env() -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []
    policy = {
        "alert_cooldown_hours": safe_positive_int(os.getenv("ALERT_COOLDOWN_HOURS"), DEFAULT_ALERT_COOLDOWN_HOURS, "ALERT_COOLDOWN_HOURS", warnings),
        "max_alert_events": safe_positive_int(os.getenv("MAX_ALERT_EVENTS"), DEFAULT_MAX_ALERT_EVENTS, "MAX_ALERT_EVENTS", warnings),
        "max_processed_alert_event_ids": safe_positive_int(os.getenv("MAX_PROCESSED_ALERT_EVENT_IDS"), DEFAULT_MAX_PROCESSED_ALERT_EVENT_IDS, "MAX_PROCESSED_ALERT_EVENT_IDS", warnings),
        "max_run_health_records": safe_positive_int(os.getenv("MAX_RUN_HEALTH_RECORDS"), DEFAULT_MAX_RUN_HEALTH_RECORDS, "MAX_RUN_HEALTH_RECORDS", warnings),
        "candidate_trend_window": safe_positive_int(os.getenv("CANDIDATE_TREND_WINDOW"), DEFAULT_CANDIDATE_TREND_WINDOW, "CANDIDATE_TREND_WINDOW", warnings),
        "candidate_collapse_ratio": safe_ratio(os.getenv("CANDIDATE_COLLAPSE_RATIO"), DEFAULT_CANDIDATE_COLLAPSE_RATIO, "CANDIDATE_COLLAPSE_RATIO", warnings),
        "candidate_collapse_consecutive_runs": safe_positive_int(os.getenv("CANDIDATE_COLLAPSE_CONSECUTIVE_RUNS"), DEFAULT_CANDIDATE_COLLAPSE_CONSECUTIVE_RUNS, "CANDIDATE_COLLAPSE_CONSECUTIVE_RUNS", warnings),
        "detail_success_rate_warning_threshold": safe_ratio(os.getenv("DETAIL_SUCCESS_RATE_WARNING_THRESHOLD"), DEFAULT_DETAIL_SUCCESS_RATE_WARNING_THRESHOLD, "DETAIL_SUCCESS_RATE_WARNING_THRESHOLD", warnings),
        "detail_success_rate_consecutive_runs": safe_positive_int(os.getenv("DETAIL_SUCCESS_RATE_CONSECUTIVE_RUNS"), DEFAULT_DETAIL_SUCCESS_RATE_CONSECUTIVE_RUNS, "DETAIL_SUCCESS_RATE_CONSECUTIVE_RUNS", warnings),
        "source_unreachable_high_threshold": safe_positive_int(os.getenv("SOURCE_UNREACHABLE_HIGH_THRESHOLD"), DEFAULT_SOURCE_UNREACHABLE_HIGH_THRESHOLD, "SOURCE_UNREACHABLE_HIGH_THRESHOLD", warnings),
        "llm_validation_high_threshold": safe_positive_int(os.getenv("LLM_VALIDATION_HIGH_THRESHOLD"), DEFAULT_LLM_VALIDATION_HIGH_THRESHOLD, "LLM_VALIDATION_HIGH_THRESHOLD", warnings),
        "runtime_warning_seconds": safe_positive_int(os.getenv("RUNTIME_WARNING_SECONDS"), DEFAULT_RUNTIME_WARNING_SECONDS, "RUNTIME_WARNING_SECONDS", warnings),
    }
    return policy, warnings


def load_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return deepcopy(default)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return deepcopy(default)
    return value if isinstance(value, dict) else deepcopy(default)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            value = json.loads(line)
            if isinstance(value, dict):
                rows.append(value)
    except (OSError, json.JSONDecodeError):
        return []
    return rows


def default_alert_state() -> dict[str, Any]:
    return {
        "version": 1,
        "stage": "4D",
        "generated_at": None,
        "bootstrap": {},
        "open_conditions": {},
        "condition_counters": {},
        "processed_event_ids": [],
        "last_processed_lifecycle_event_at": None,
        "last_processed_run_id": None,
        "last_applied_run_id": None,
        "last_applied_started_at": None,
    }


def build_alert_key(alert_type: str, source_id: str | None, record_id: str | None) -> str:
    return "|".join((str(alert_type), str(source_id or "global"), str(record_id or "global")))


def _alert_event_id(run_id: str, alert_key: str, action: str, related_event_id: object = None) -> str:
    raw = f"{run_id}|{alert_key}|{action}|{related_event_id or ''}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


def _source_map(value: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    value = value or {}
    sources = value.get("sources", value)
    return sources if isinstance(sources, dict) else {}


def _llm_status(audit: dict[str, Any] | None) -> tuple[str, str]:
    audit = audit or {}
    if audit.get("llm_enabled") is False:
        return "skipped_disabled", str(audit.get("validation_status") or "not_run")
    return str(audit.get("llm_status") or audit.get("status") or "unknown"), str(audit.get("validation_status") or "unknown")


def _detail_totals(item_report: dict[str, Any] | None) -> tuple[int, int]:
    success = failed = 0
    for source in _source_map(item_report).values():
        success += int(source.get("final_detail_success") or source.get("detail_fetch_success") or 0)
        failed += int(source.get("final_detail_failed") or source.get("detail_fetch_failed") or 0)
    return success, failed


def _condition_spec(
    alert_type: str,
    *,
    source_id: str | None = None,
    record_id: str | None = None,
    canonical_url: str | None = None,
    severity: str = "warning",
    category: str = "operations",
    consecutive: int = 1,
    reason: str | None = None,
    attention_required: bool = False,
) -> dict[str, Any]:
    return {
        "alert_key": build_alert_key(alert_type, source_id, record_id),
        "alert_type": alert_type,
        "alert_kind": "condition",
        "category": category,
        "severity": severity,
        "source_id": source_id,
        "record_id": record_id,
        "canonical_url": canonical_url,
        "consecutive_observations": max(1, int(consecutive)),
        "message_code": alert_type,
        "reason": reason or alert_type,
        "attention_required": bool(attention_required),
    }


def _append_alert_event(
    target: list[dict[str, Any]],
    *,
    run_id: str,
    occurred_at: str,
    action: str,
    spec: dict[str, Any],
    related_event_id: object = None,
) -> None:
    event_id = _alert_event_id(run_id, str(spec["alert_key"]), action, related_event_id)
    if any(str(item.get("alert_event_id")) == event_id for item in target):
        return
    target.append(
        {
            "alert_event_id": event_id,
            "run_id": run_id,
            "occurred_at": occurred_at,
            "action": action,
            "alert_key": spec.get("alert_key"),
            "alert_type": spec.get("alert_type"),
            "alert_kind": spec.get("alert_kind", "condition"),
            "category": spec.get("category"),
            "severity": spec.get("severity"),
            "source_id": spec.get("source_id"),
            "record_id": spec.get("record_id"),
            "canonical_url": spec.get("canonical_url"),
            "lifecycle_event_id": related_event_id,
            "consecutive_observations": spec.get("consecutive_observations", 1),
            "message_code": spec.get("message_code"),
            "reason": spec.get("reason"),
            "attention_required": bool(spec.get("attention_required")),
        }
    )


def _candidate_history(history: list[dict[str, Any]], source_id: str, window: int) -> list[int]:
    values: list[int] = []
    for row in history[-window:]:
        complete = row.get("candidate_complete", {})
        if isinstance(complete, dict) and complete.get(source_id) is False:
            continue
        counts = row.get("candidate_counts", {})
        if isinstance(counts, dict) and isinstance(counts.get(source_id), int):
            values.append(int(counts[source_id]))
    return values


def evaluate_alerts_data(
    *,
    lifecycle_events: list[dict[str, Any]],
    lifecycle_state: dict[str, Any],
    lifecycle_report: dict[str, Any],
    source_status: dict[str, Any],
    item_extraction_report: dict[str, Any],
    llm_audit: dict[str, Any],
    run_context: dict[str, Any],
    previous_state: dict[str, Any] | None = None,
    existing_alert_events: list[dict[str, Any]] | None = None,
    health_history: list[dict[str, Any]] | None = None,
    policy: dict[str, Any] | None = None,
) -> AlertEvaluation:
    policy = {**policy_from_env()[0], **(policy or {})}
    state = deepcopy(previous_state or default_alert_state())
    state.setdefault("open_conditions", {})
    state.setdefault("condition_counters", {})
    state.setdefault("processed_event_ids", [])
    all_existing = deepcopy(existing_alert_events or [])
    history = health_history or []
    run_id = str(run_context.get("run_id") or "")
    started_at = str(run_context.get("started_at") or run_context.get("generated_at") or "")
    parsed_started = parse_datetime(started_at)
    previous_started = parse_datetime(state.get("last_applied_started_at"))
    if not run_id or parsed_started is None:
        warning = "运行上下文缺少有效 run_id 或 started_at，告警状态未写入。"
        return AlertEvaluation(state, all_existing, {"stage": "4D", "overall_alert_status": "critical", "warnings": [warning]}, [], [warning], False)
    if str(state.get("last_applied_run_id") or "") != run_id and previous_started is not None and parsed_started < previous_started:
        spec = _condition_spec("stale_run_ignored", severity="warning", reason="older_run_did_not_overwrite_alert_state")
        transient: list[dict[str, Any]] = []
        _append_alert_event(transient, run_id=run_id, occurred_at=started_at, action="notify", spec=spec)
        report = _build_alert_report(run_id, started_at, transient, state.get("open_conditions", {}), ["stale_run_ignored"])
        report["stale_run_ignored"] = True
        return AlertEvaluation(state, all_existing, report, transient, ["stale_run_ignored"], False)

    processed = [str(value) for value in state.get("processed_event_ids", []) if value]
    processed_set = set(processed)
    new_events: list[dict[str, Any]] = []
    bootstrap = state.setdefault("bootstrap", {})
    if not bootstrap.get("initialized"):
        ids = [str(event.get("event_id")) for event in lifecycle_events if event.get("event_id")]
        processed.extend(value for value in ids if value not in processed_set)
        processed_set.update(ids)
        bootstrap.update(
            {
                "initialized": True,
                "initialized_at": started_at,
                "lifecycle_event_watermark_count": len(ids),
            }
        )
    else:
        for event in lifecycle_events:
            lifecycle_event_id = str(event.get("event_id") or "")
            if not lifecycle_event_id or lifecycle_event_id in processed_set:
                continue
            event_type = str(event.get("event_type") or "")
            rule = EVENT_NOTIFICATION_RULES.get(event_type)
            if rule:
                severity, category = rule
                spec = {
                    "alert_key": build_alert_key(event_type, event.get("source_id"), event.get("record_id")),
                    "alert_type": event_type,
                    "alert_kind": "event",
                    "category": category,
                    "severity": severity,
                    "source_id": event.get("source_id"),
                    "record_id": event.get("record_id"),
                    "canonical_url": event.get("canonical_url"),
                    "consecutive_observations": 1,
                    "message_code": event_type,
                    "reason": "deterministic_lifecycle_event_notification",
                    "attention_required": severity in {"high", "critical"},
                }
                _append_alert_event(new_events, run_id=run_id, occurred_at=started_at, action="notify", spec=spec, related_event_id=lifecycle_event_id)
            processed.append(lifecycle_event_id)
            processed_set.add(lifecycle_event_id)

    current_conditions: dict[str, dict[str, Any]] = {}
    observed_types: set[str] = set()
    lifecycle_items = lifecycle_state.get("items", {}) if isinstance(lifecycle_state.get("items"), dict) else {}
    if lifecycle_items:
        observed_types.update({"temporarily_missing", "long_absent", "detail_fetch_failed"})
    for item in lifecycle_items.values():
        lifecycle_name = str(item.get("lifecycle_state") or "")
        if lifecycle_name == "temporarily_missing":
            spec = _condition_spec("temporarily_missing", source_id=item.get("source_id"), record_id=item.get("record_id"), canonical_url=item.get("canonical_url"), severity="warning", category="collection", consecutive=int(item.get("consecutive_missing_observations") or 1), reason="not_observed_in_complete_index_not_deleted")
        elif lifecycle_name == "long_absent":
            spec = _condition_spec("long_absent", source_id=item.get("source_id"), record_id=item.get("record_id"), canonical_url=item.get("canonical_url"), severity="high", category="collection", consecutive=int(item.get("consecutive_missing_observations") or 1), reason="long_absence_is_not_official_deletion", attention_required=True)
        elif lifecycle_name == "fetch_failed":
            failures = int(item.get("consecutive_detail_failures") or 1)
            spec = _condition_spec("detail_fetch_failed", source_id=item.get("source_id"), record_id=item.get("record_id"), canonical_url=item.get("canonical_url"), severity="high" if failures >= 3 else "warning", category="collection", consecutive=failures, reason="collector_failed_historical_data_retained", attention_required=failures >= 3)
        else:
            continue
        current_conditions[str(spec["alert_key"])] = spec

    sources = _source_map(source_status)
    if sources:
        observed_types.update({"source_unreachable", "candidate_discovery_degraded"})
    for source_id, source in sources.items():
        reachable = bool(source.get("reachable"))
        if not reachable:
            key = build_alert_key("source_unreachable", source_id, None)
            previous_count = int(state.get("condition_counters", {}).get(key, 0))
            count = previous_count if state.get("open_conditions", {}).get(key, {}).get("last_observed_run_id") == run_id else previous_count + 1
            state["condition_counters"][key] = count
            high_at = int(policy["source_unreachable_high_threshold"])
            spec = _condition_spec("source_unreachable", source_id=source_id, severity="high" if count >= high_at else "warning", category="source_access", consecutive=count, reason="collector_could_not_reach_official_source_not_service_outage", attention_required=count >= high_at)
            current_conditions[key] = spec
        else:
            state["condition_counters"][build_alert_key("source_unreachable", source_id, None)] = 0

        if reachable and bool(source.get("index_observation_complete")):
            current_count = source.get("candidate_count")
            historical = _candidate_history(history, source_id, int(policy["candidate_trend_window"]))
            key = build_alert_key("candidate_discovery_degraded", source_id, None)
            collapsed = (
                isinstance(current_count, int)
                and len(historical) >= 3
                and median(historical) > 0
                and current_count < median(historical) * float(policy["candidate_collapse_ratio"])
            )
            count = int(state["condition_counters"].get(key, 0)) + 1 if collapsed else 0
            state["condition_counters"][key] = count
            if count >= int(policy["candidate_collapse_consecutive_runs"]):
                spec = _condition_spec("candidate_discovery_degraded", source_id=source_id, severity="warning", category="candidate_discovery", consecutive=count, reason="candidate_count_below_rolling_median_not_official_deletion")
                current_conditions[key] = spec

    success, failed = _detail_totals(item_extraction_report)
    if success + failed > 0:
        observed_types.add("detail_success_rate_degraded")
        rate = success / (success + failed)
        key = build_alert_key("detail_success_rate_degraded", None, None)
        low = rate < float(policy["detail_success_rate_warning_threshold"])
        count = int(state["condition_counters"].get(key, 0)) + 1 if low else 0
        state["condition_counters"][key] = count
        if count >= int(policy["detail_success_rate_consecutive_runs"]):
            severity = "high" if count >= 3 and rate == 0 else "warning"
            current_conditions[key] = _condition_spec("detail_success_rate_degraded", severity=severity, category="extraction", consecutive=count, reason="collector_detail_success_rate_degraded", attention_required=severity == "high")

    llm_status, validation_status = _llm_status(llm_audit)
    llm_key = build_alert_key("llm_validation_failed", None, None)
    if validation_status == "failed" or llm_status == "validation_failed":
        observed_types.add("llm_validation_failed")
        count = int(state["condition_counters"].get(llm_key, 0)) + (0 if state.get("open_conditions", {}).get(llm_key, {}).get("last_observed_run_id") == run_id else 1)
        state["condition_counters"][llm_key] = count
        high_at = int(policy["llm_validation_high_threshold"])
        current_conditions[llm_key] = _condition_spec("llm_validation_failed", severity="high" if count >= high_at else "warning", category="llm_validation", consecutive=count, reason="model_output_failed_local_source_validation", attention_required=count >= high_at)
    elif llm_status == "generated" and validation_status == "passed":
        observed_types.add("llm_validation_failed")
        state["condition_counters"][llm_key] = 0

    status_rules = (
        ("email_delivery_failed", "email_status", "email", "email_delivery_failed"),
        ("gitee_sync_failed", "gitee_status", "distribution", "gitee_sync_failed_non_blocking"),
        ("output_validation_failed", "output_check_status", "integrity", "output_validation_failed"),
        ("project_audit_failed", "project_audit_status", "integrity", "project_audit_failed"),
        ("state_integrity_failed", "state_integrity_status", "integrity", "state_integrity_failed"),
        ("transaction_failed", "transaction_status", "integrity", "transaction_failed"),
        ("stable_id_collision", "stable_id_status", "integrity", "stable_id_collision"),
    )
    for alert_type, context_key, category, reason in status_rules:
        status = str(run_context.get(context_key) or "unknown").lower()
        if status not in {"success", "passed", "failed"}:
            continue
        observed_types.add(alert_type)
        if status == "failed":
            severity = "critical" if alert_type in INTEGRITY_ALERT_TYPES else "warning"
            spec = _condition_spec(alert_type, severity=severity, category=category, reason=reason, attention_required=severity == "critical")
            current_conditions[str(spec["alert_key"])] = spec

    if lifecycle_report:
        observed_types.add("stale_run_ignored")
        if lifecycle_report.get("stale_run_ignored") is True:
            spec = _condition_spec(
                "stale_run_ignored",
                severity="warning",
                category="state_ordering",
                reason="older_run_was_rejected_without_overwriting_newer_state",
            )
            current_conditions[str(spec["alert_key"])] = spec

    open_conditions = state["open_conditions"]
    cooldown = timedelta(hours=int(policy["alert_cooldown_hours"]))
    for key, spec in current_conditions.items():
        previous = open_conditions.get(key)
        if previous is None:
            opened = {
                **spec,
                "status": "open",
                "first_opened_at": started_at,
                "last_observed_at": started_at,
                "last_notified_at": started_at,
                "last_observed_run_id": run_id,
                "occurrence_count": 1,
                "cooldown_until": (parsed_started + cooldown).isoformat(timespec="seconds"),
            }
            open_conditions[key] = opened
            _append_alert_event(new_events, run_id=run_id, occurred_at=started_at, action="open", spec=opened)
            continue
        previous_rank = SEVERITY_RANK.get(str(previous.get("severity")), 0)
        current_rank = SEVERITY_RANK.get(str(spec.get("severity")), 0)
        same_run = str(previous.get("last_observed_run_id") or "") == run_id
        previous.update(spec)
        previous["status"] = "open"
        previous["last_observed_at"] = started_at
        previous["last_observed_run_id"] = run_id
        if not same_run:
            previous["occurrence_count"] = int(previous.get("occurrence_count") or 0) + 1
        if current_rank > previous_rank:
            previous["last_notified_at"] = started_at
            previous["cooldown_until"] = (parsed_started + cooldown).isoformat(timespec="seconds")
            _append_alert_event(new_events, run_id=run_id, occurred_at=started_at, action="escalate", spec=previous)
        elif not same_run and (parse_datetime(previous.get("cooldown_until")) or parsed_started) <= parsed_started:
            previous["last_notified_at"] = started_at
            previous["cooldown_until"] = (parsed_started + cooldown).isoformat(timespec="seconds")
            _append_alert_event(new_events, run_id=run_id, occurred_at=started_at, action="update", spec=previous)
        elif not same_run:
            _append_alert_event(new_events, run_id=run_id, occurred_at=started_at, action="suppress", spec=previous)

    for key, previous in list(open_conditions.items()):
        if key in current_conditions or str(previous.get("alert_type")) not in observed_types:
            continue
        resolved = {**previous, "status": "resolved", "severity": previous.get("severity", "warning")}
        _append_alert_event(new_events, run_id=run_id, occurred_at=started_at, action="resolve", spec=resolved)
        del open_conditions[key]
        state["condition_counters"][key] = 0

    event_by_id = {str(item.get("alert_event_id")): item for item in [*all_existing, *new_events] if item.get("alert_event_id")}
    ordered_ids: list[str] = []
    for item in [*all_existing, *new_events]:
        identity = str(item.get("alert_event_id") or "")
        if identity and identity not in ordered_ids:
            ordered_ids.append(identity)
    max_events = int(policy["max_alert_events"])
    preserved_open_keys = set(open_conditions)
    recent_ids = ordered_ids[-max_events:]
    for identity in ordered_ids:
        if str(event_by_id[identity].get("alert_key")) in preserved_open_keys and identity not in recent_ids:
            recent_ids.insert(0, identity)
    all_events = [event_by_id[identity] for identity in recent_ids[-max_events:]]
    processed = processed[-int(policy["max_processed_alert_event_ids"]):]
    state.update(
        {
            "version": 1,
            "stage": "4D",
            "generated_at": started_at,
            "processed_event_ids": processed,
            "last_processed_lifecycle_event_at": max((str(item.get("occurred_at") or "") for item in lifecycle_events), default=state.get("last_processed_lifecycle_event_at")),
            "last_processed_run_id": run_id,
            "last_applied_run_id": run_id,
            "last_applied_started_at": started_at,
        }
    )
    report = _build_alert_report(run_id, started_at, new_events, open_conditions, [])
    report["bootstrap_performed"] = bootstrap.get("initialized_at") == started_at
    report["severity_safety_note"] = SEVERITY_SAFETY_NOTE
    return AlertEvaluation(state, all_events, report, new_events)


def _build_alert_report(
    run_id: str,
    generated_at: str,
    alerts_this_run: list[dict[str, Any]],
    open_conditions: dict[str, dict[str, Any]],
    warnings: list[str],
) -> dict[str, Any]:
    actions = {action: sum(1 for item in alerts_this_run if item.get("action") == action) for action in ALERT_ACTIONS}
    open_severity = {severity: sum(1 for item in open_conditions.values() if item.get("severity") == severity) for severity in ALERT_SEVERITIES}
    run_severity = {severity: sum(1 for item in alerts_this_run if item.get("severity") == severity and item.get("action") != "suppress") for severity in ALERT_SEVERITIES}
    critical = open_severity["critical"] + run_severity["critical"]
    high = open_severity["high"] + run_severity["high"]
    warning = open_severity["warning"] + run_severity["warning"]
    status = "critical" if critical else "high_attention" if high else "attention" if warning else "normal"
    return {
        "version": 1,
        "stage": "4D",
        "generated_at": generated_at,
        "run_id": run_id,
        "overall_alert_status": status,
        "totals": {
            "new_notifications": actions["notify"],
            "opened": actions["open"],
            "updated": actions["update"],
            "escalated": actions["escalate"],
            "resolved": actions["resolve"],
            "suppressed": actions["suppress"],
            "open_conditions": len(open_conditions),
            **run_severity,
            **{f"open_{key}": value for key, value in open_severity.items()},
        },
        "alerts_this_run": deepcopy(alerts_this_run),
        "open_alerts": [deepcopy(open_conditions[key]) for key in sorted(open_conditions)],
        "warnings": warnings,
        "severity_safety_note": SEVERITY_SAFETY_NOTE,
    }


def build_run_health_data(
    *,
    source_status: dict[str, Any],
    item_extraction_report: dict[str, Any],
    lifecycle_report: dict[str, Any],
    llm_audit: dict[str, Any],
    alert_report: dict[str, Any],
    run_context: dict[str, Any],
    previous_history: list[dict[str, Any]] | None = None,
    policy: dict[str, Any] | None = None,
) -> HealthEvaluation:
    policy = {**policy_from_env()[0], **(policy or {})}
    run_id = str(run_context.get("run_id") or "")
    started_at = str(run_context.get("started_at") or "")
    finished_at = str(run_context.get("finished_at") or started_at)
    start = parse_datetime(started_at)
    finish = parse_datetime(finished_at)
    if not run_id or start is None or finish is None:
        return HealthEvaluation({"stage": "4D", "overall_health": "unhealthy", "warnings": ["运行健康上下文时间无效。"]}, deepcopy(previous_history or []), False, ["invalid_run_context"])
    history = deepcopy(previous_history or [])
    newer = [parse_datetime(row.get("generated_at")) for row in history if str(row.get("run_id")) != run_id]
    latest = max((value for value in newer if value is not None), default=None)
    if latest is not None and start < latest:
        return HealthEvaluation({"stage": "4D", "run_id": run_id, "overall_health": "degraded", "stale_run_ignored": True, "warnings": ["旧运行未覆盖较新的健康状态。"]}, history, False, ["stale_run_ignored"])

    sources = _source_map(source_status)
    reachable = sum(1 for source in sources.values() if source.get("reachable") is True)
    total_sources = len(sources)
    complete = sum(1 for source in sources.values() if source.get("index_observation_complete") is True)
    success, failed = _detail_totals(item_extraction_report)
    detail_total = success + failed
    success_rate = success / detail_total if detail_total else None
    llm_status, validation_status = _llm_status(llm_audit)
    llm_disabled = llm_status in {"skipped_disabled", "disabled", "not_enabled"}
    totals = alert_report.get("totals", {}) if isinstance(alert_report.get("totals"), dict) else {}

    def status_component(raw: object, *, disabled_ok: bool = False) -> str:
        value = str(raw or "unknown").lower()
        if value in {"success", "passed", "healthy"} or disabled_ok and value in {"disabled", "skipped", "skipped_disabled"}:
            return "healthy"
        if value in {"failed", "degraded", "warning"}:
            return "degraded"
        return "unknown"

    output_status = status_component(run_context.get("output_check_status"))
    audit_status = status_component(run_context.get("project_audit_status"))
    if str(run_context.get("output_check_status") or "").lower() == "failed":
        output_status = "unhealthy"
    if str(run_context.get("project_audit_status") or "").lower() == "failed":
        audit_status = "unhealthy"
    components = {
        "source_collection": {"status": "healthy" if total_sources and reachable == total_sources else "degraded" if total_sources else "unknown", "reachable_sources": reachable, "total_sources": total_sources},
        "candidate_discovery": {"status": "healthy" if total_sources and complete == total_sources else "degraded" if total_sources else "unknown", "complete_sources": complete, "total_sources": total_sources},
        "detail_extraction": {"status": "healthy" if success_rate is not None and success_rate >= float(policy["detail_success_rate_warning_threshold"]) else "degraded" if success_rate is not None else "unknown", "success": success, "failed": failed, "success_rate": success_rate},
        "lifecycle": {"status": "degraded" if lifecycle_report.get("stale_run_ignored") or (lifecycle_report.get("attention_items") or []) else "healthy"},
        "llm": {"status": "healthy" if llm_disabled or (llm_status == "generated" and validation_status == "passed") else "degraded" if validation_status == "failed" else "unknown", "enabled": not llm_disabled, "result": llm_status},
        "output_validation": {"status": output_status},
        "project_audit": {"status": audit_status},
        "email": {"status": status_component(run_context.get("email_status"), disabled_ok=True), "result": str(run_context.get("email_status") or "unknown")},
        "gitee_sync": {"status": status_component(run_context.get("gitee_status"), disabled_ok=True), "result": str(run_context.get("gitee_status") or "unknown")},
    }
    open_warning = int(totals.get("open_warning") or 0)
    open_high = int(totals.get("open_high") or 0)
    open_critical = int(totals.get("open_critical") or 0)
    overall = "unhealthy" if open_critical or output_status == "unhealthy" or audit_status == "unhealthy" else "degraded" if open_high or open_warning or any(component["status"] == "degraded" for component in components.values()) else "healthy"
    duration = max(0.0, (finish - start).total_seconds())
    warnings: list[str] = []
    if duration > int(policy["runtime_warning_seconds"]):
        warnings.append("运行时间超过公开配置阈值，需要检查自动化性能。")
        if overall == "healthy":
            overall = "degraded"
    health = {
        "version": 1,
        "stage": "4D",
        "generated_at": finished_at,
        "run_id": run_id,
        "last_applied_run_id": run_id,
        "last_applied_started_at": started_at,
        "overall_health": overall,
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_seconds": duration,
        "components": components,
        "alert_summary": {"open_warning": open_warning, "open_high": open_high, "open_critical": open_critical},
        "warnings": warnings,
        "severity_safety_note": SEVERITY_SAFETY_NOTE,
    }
    candidate_counts = {source_id: int(source.get("candidate_count") or 0) for source_id, source in sources.items()}
    candidate_complete = {source_id: bool(source.get("index_observation_complete")) for source_id, source in sources.items()}
    lifecycle_totals = lifecycle_report.get("totals", {}) if isinstance(lifecycle_report.get("totals"), dict) else {}
    history_row = {
        "run_id": run_id,
        "generated_at": finished_at,
        "overall_health": overall,
        "duration_seconds": duration,
        "reachable_sources": reachable,
        "total_sources": total_sources,
        "candidate_counts": candidate_counts,
        "candidate_complete": candidate_complete,
        "detail_success_rate": success_rate,
        "new_items": int(lifecycle_totals.get("new") or 0),
        "changed_items": int(lifecycle_totals.get("changed") or 0),
        "fetch_failed": int(lifecycle_totals.get("detail_fetch_failed") or 0),
        "open_warning": open_warning,
        "open_high": open_high,
        "open_critical": open_critical,
        "llm_status": llm_status,
        "email_status": str(run_context.get("email_status") or "unknown"),
        "gitee_status": str(run_context.get("gitee_status") or "unknown"),
    }
    history = [row for row in history if str(row.get("run_id")) != run_id]
    history.append(history_row)
    history = history[-int(policy["max_run_health_records"]):]
    return HealthEvaluation(health, history)


def _json_text(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _jsonl_text(rows: Iterable[dict[str, Any]]) -> str:
    return "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows)


def atomic_write_bundle(payloads: dict[Path, str]) -> None:
    temporary: dict[Path, Path] = {}
    backups: dict[Path, bytes | None] = {}
    replaced: list[Path] = []
    try:
        for path, content in payloads.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            temp = path.with_suffix(path.suffix + ".phase4d.tmp")
            temp.write_text(content, encoding="utf-8", newline="\n")
            temporary[path] = temp
            backups[path] = path.read_bytes() if path.exists() else None
        for path, temp in temporary.items():
            os.replace(temp, path)
            replaced.append(path)
    except Exception:
        for path in reversed(replaced):
            previous = backups.get(path)
            if previous is None:
                path.unlink(missing_ok=True)
            else:
                restore = path.with_suffix(path.suffix + ".phase4d.restore")
                restore.write_bytes(previous)
                os.replace(restore, path)
        raise
    finally:
        for path in [*temporary.values(), *(path.with_suffix(path.suffix + ".phase4d.restore") for path in payloads)]:
            path.unlink(missing_ok=True)


def write_alert_evaluation(
    evaluation: AlertEvaluation,
    *,
    state_path: Path = ALERT_STATE_FILE,
    events_path: Path = ALERT_EVENTS_FILE,
    report_path: Path = ALERT_REPORT_FILE,
) -> None:
    if not evaluation.write_allowed:
        return
    atomic_write_bundle(
        {
            state_path: _json_text(evaluation.state),
            events_path: _jsonl_text(evaluation.all_events),
            report_path: _json_text(evaluation.report),
        }
    )


def write_health_evaluation(
    evaluation: HealthEvaluation,
    *,
    health_path: Path = RUN_HEALTH_FILE,
    history_path: Path = RUN_HEALTH_HISTORY_FILE,
) -> None:
    if not evaluation.write_allowed:
        return
    atomic_write_bundle({health_path: _json_text(evaluation.health), history_path: _jsonl_text(evaluation.history)})
