import pytest

from telemetry.schema_contract import validate_record


def test_window_observation_requires_scheduler_version_and_policy_hash():
    record = {
        "schema_version": "v1",
        "window_id": "w1",
        "timestamp_us": 123,
    }

    with pytest.raises(ValueError, match=r"window_observation missing required key: scheduler_version"):
        validate_record("window_observation", record)


@pytest.mark.parametrize(
    ("mutated_record", "missing_key"),
    [
        (
            {
                "schema_version": "v1",
                "window_id": "w1",
                "timestamp_us": 123,
                "scheduler_version": "sched-1",
            },
            "policy_hash",
        ),
        (
            {
                "schema_version": "v1",
                "window_id": "w1",
                "timestamp_us": 123,
                "policy_hash": "abc123",
            },
            "scheduler_version",
        ),
    ],
)
def test_window_observation_rejects_missing_required_keys(mutated_record, missing_key):
    with pytest.raises(
        ValueError,
        match=rf"window_observation missing required key: {missing_key}",
    ):
        validate_record("window_observation", mutated_record)


def test_task_arrival_requires_poisson_metadata():
    record = {
        "schema_version": "v1",
        "experiment_id": "20260421-120000",
        "event_id": "e1",
        "event_type": "TASK_ARRIVAL",
        "timestamp_us": 1,
        "window_id": "w1",
        "task_id": "t1",
        "request_id": "r1",
        "task_type": "LOCAL_TOOL",
        "source": "generator",
        "arrival_source": "poisson",
        "generator_seed": 42,
        "lambda_per_sec": 4.0,
    }

    validate_record("task_events", record)
