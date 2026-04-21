import json

import pytest

from telemetry.trace_sink import TraceSink


PLAN_RECORD = {
    "schema_version": "v1",
    "plan_id": "plan-1",
    "window_id": "window-1",
    "generated_at_us": 123,
    "scheduler_version": "sched-1",
    "policy_hash": "abc123",
}


def test_trace_sink_writes_plan_jsonl(tmp_path):
    sink = TraceSink(root_dir=tmp_path, experiment_id="exp-123")

    sink.write("plan", PLAN_RECORD)

    path = tmp_path / "exp-123" / "plan.jsonl"
    assert path.read_text(encoding="utf-8").splitlines() == [json.dumps(PLAN_RECORD, ensure_ascii=True)]


def test_trace_sink_appends_without_overwrite(tmp_path):
    sink = TraceSink(root_dir=tmp_path, experiment_id="exp-123")

    sink.write("plan", PLAN_RECORD)
    sink.write("plan", {**PLAN_RECORD, "plan_id": "plan-2"})

    path = tmp_path / "exp-123" / "plan.jsonl"
    assert path.read_text(encoding="utf-8").splitlines() == [
        json.dumps(PLAN_RECORD, ensure_ascii=True),
        json.dumps({**PLAN_RECORD, "plan_id": "plan-2"}, ensure_ascii=True),
    ]


@pytest.mark.parametrize(
    ("kind", "record", "expected_message"),
    [
        (
            "plan",
            {
                "schema_version": "v1",
                "plan_id": "plan-1",
                "window_id": "window-1",
                "generated_at_us": 123,
                "scheduler_version": "sched-1",
            },
            r"plan missing required key: policy_hash",
        ),
        (
            "window_observation",
            {
                "schema_version": "v1",
                "window_id": "window-1",
                "timestamp_us": 123,
                "scheduler_version": "sched-1",
                "policy_hash": "abc123",
            },
            None,
        ),
    ],
)
def test_trace_sink_validates_records_before_write(tmp_path, kind, record, expected_message):
    sink = TraceSink(root_dir=tmp_path, experiment_id="exp-123")

    if expected_message is None:
        sink.write(kind, record)
        assert (tmp_path / "exp-123" / "window_observation.jsonl").exists()
        return

    with pytest.raises(ValueError, match=expected_message):
        sink.write(kind, record)
