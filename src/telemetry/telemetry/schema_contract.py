from __future__ import annotations

from collections.abc import Mapping


REQUIRED_KEYS = {
    "window_observation": (
        "schema_version",
        "window_id",
        "timestamp_us",
        "scheduler_version",
        "policy_hash",
    ),
    "plan": (
        "schema_version",
        "plan_id",
        "window_id",
        "generated_at_us",
        "scheduler_version",
        "policy_hash",
    ),
    "outcome": (
        "schema_version",
        "outcome_id",
        "window_id",
        "plan_id",
        "scheduler_version",
        "policy_hash",
    ),
    "task_events": (
        "schema_version",
        "experiment_id",
        "event_id",
        "event_type",
        "timestamp_us",
        "window_id",
        "task_id",
        "request_id",
        "task_type",
        "source",
    ),
    "resource_samples": (
        "schema_version",
        "experiment_id",
        "sample_id",
        "timestamp_us",
        "window_id",
        "scope",
        "cpu",
        "memory",
        "gpu",
        "network",
    ),
}


def _require_mapping(record: Mapping[str, object]) -> Mapping[str, object]:
    if not isinstance(record, Mapping):
        raise ValueError("record must be a mapping")
    return record


def validate_record(kind: str, record: Mapping[str, object]) -> None:
    record = _require_mapping(record)

    if kind not in REQUIRED_KEYS:
        raise ValueError(f"unknown trace kind: {kind}")

    missing_keys = [key for key in REQUIRED_KEYS[kind] if key not in record]
    if missing_keys:
        raise ValueError(f"{kind} missing required key: {missing_keys[0]}")

    if record.get("schema_version") != "v1":
        raise ValueError(f"{kind} requires schema_version=v1")

    if kind == "task_events" and record.get("event_type") == "TASK_ARRIVAL":
        for key in ("arrival_source", "generator_seed", "lambda_per_sec"):
            if key not in record:
                raise ValueError(f"task_events missing required key: {key}")
