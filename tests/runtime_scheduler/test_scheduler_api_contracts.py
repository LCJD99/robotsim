from runtime_scheduler.scheduler_api.contracts import (
    CommandEventStatus,
    NodeActivation,
    TaskSnapshot,
    TaskState,
)


def test_task_snapshot_requires_task_id_and_positive_version() -> None:
    try:
        TaskSnapshot(
            task_id="",
            app_type="perception_recognition_app",
            task_type="recognize_objects",
            version=0,
            timestamp_ms=123,
            task_state=TaskState.PENDING,
            criticality="critical",
            node_refs=[],
            edge_refs=[],
        )
    except ValueError as exc:
        assert "task_id" in str(exc) or "version" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_command_event_status_enum_contains_required_states() -> None:
    assert CommandEventStatus.ACCEPTED.value == "accepted"
    assert CommandEventStatus.PARTIALLY_APPLIED.value == "partially_applied"


def test_node_activation_has_required_and_optional_only() -> None:
    values = {member.value for member in NodeActivation}
    assert values == {"required", "optional"}
