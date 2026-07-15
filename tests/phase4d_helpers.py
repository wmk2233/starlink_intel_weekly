from __future__ import annotations

from copy import deepcopy

from scripts.operational_health import default_alert_state, evaluate_alerts_data


FIXTURE_SOURCE = "fixture_official_updates"
FIXTURE_URL = "https://example.invalid/updates/item-a"


def lifecycle_event(event_id: str, event_type: str = "item_discovered", run_id: str = "lifecycle-run") -> dict:
    return {
        "event_id": event_id,
        "run_id": run_id,
        "occurred_at": "2026-01-01T00:00:00+00:00",
        "event_type": event_type,
        "record_id": "fixture-item-a",
        "source_id": FIXTURE_SOURCE,
        "canonical_url": FIXTURE_URL,
    }


def lifecycle_state(state: str = "active", failures: int = 0) -> dict:
    return {
        "stage": "4D",
        "items": {
            "fixture-item-a": {
                "record_id": "fixture-item-a",
                "source_id": FIXTURE_SOURCE,
                "canonical_url": FIXTURE_URL,
                "lifecycle_state": state,
                "consecutive_missing_observations": 1 if state in {"temporarily_missing", "long_absent"} else 0,
                "consecutive_detail_failures": failures,
                "attention_required": failures >= 3 or state == "long_absent",
            }
        },
    }


def source_status(*, reachable: bool = True, candidate_count: int = 4, complete: bool = True) -> dict:
    return {
        "sources": {
            FIXTURE_SOURCE: {
                "reachable": reachable,
                "candidate_count": candidate_count,
                "index_observation_complete": complete,
            }
        }
    }


def item_report(success: int = 4, failed: int = 0) -> dict:
    return {
        "sources": {
            FIXTURE_SOURCE: {
                "final_detail_success": success,
                "final_detail_failed": failed,
            }
        }
    }


def context(run_id: str, started_at: str, **statuses) -> dict:
    return {
        "run_id": run_id,
        "started_at": started_at,
        "finished_at": started_at,
        "email_status": "disabled",
        "gitee_status": "skipped",
        "output_check_status": "passed",
        "project_audit_status": "passed",
        **statuses,
    }


def policy(**overrides) -> dict:
    return {
        "alert_cooldown_hours": 24,
        "max_alert_events": 2000,
        "max_processed_alert_event_ids": 2000,
        "max_run_health_records": 400,
        "candidate_trend_window": 8,
        "candidate_collapse_ratio": 0.25,
        "candidate_collapse_consecutive_runs": 2,
        "detail_success_rate_warning_threshold": 0.5,
        "detail_success_rate_consecutive_runs": 2,
        "source_unreachable_high_threshold": 2,
        "llm_validation_high_threshold": 3,
        "runtime_warning_seconds": 900,
        **overrides,
    }


def evaluate(
    *,
    run_id: str,
    started_at: str,
    events: list[dict] | None = None,
    state: dict | None = None,
    previous_alert_state: dict | None = None,
    alert_events: list[dict] | None = None,
    sources: dict | None = None,
    details: dict | None = None,
    llm: dict | None = None,
    history: list[dict] | None = None,
    statuses: dict | None = None,
    config: dict | None = None,
    phase: str = "final",
):
    run_context = context(run_id, started_at, **(statuses or {}))
    run_context["health_phase"] = phase
    return evaluate_alerts_data(
        lifecycle_events=deepcopy(events or []),
        lifecycle_state=deepcopy(state or lifecycle_state()),
        lifecycle_report={"stage": "4D", "events_this_run": []},
        source_status=deepcopy(sources or source_status()),
        item_extraction_report=deepcopy(details or item_report()),
        llm_audit=deepcopy(llm or {"llm_status": "skipped_disabled", "validation_status": "not_run"}),
        run_context=run_context,
        previous_state=deepcopy(previous_alert_state or default_alert_state()),
        existing_alert_events=deepcopy(alert_events or []),
        health_history=deepcopy(history or []),
        policy=policy(**(config or {})),
    )
