from runtime_scheduler.scheduler_api.control import (
    CommandCoordinator,
    CommandPayload,
    validate_sync_command,
)
from runtime_scheduler.scheduler_api.errors import ApiError
from runtime_scheduler.scheduler_api.registry import NodeSpec, NumericBounds


def test_validate_sync_command_rejects_out_of_bounds_cpu_quota() -> None:
    node_spec = NodeSpec(
        node_id="planner",
        cpu_quota=NumericBounds(min_value=0.1, max_value=2.0),
        max_concurrency=NumericBounds(min_value=1, max_value=8),
    )

    try:
        validate_sync_command(node_spec, "cpu_quota", 2.5)
    except ApiError as exc:
        assert exc.code == "INVALID_ARG"
        assert exc.details.get("reason") == "bound_violation"
        assert exc.details.get("field") == "cpu_quota"
    else:
        raise AssertionError("expected ApiError for out-of-bounds cpu_quota")


def test_same_command_id_same_payload_returns_same_result() -> None:
    coordinator = CommandCoordinator()
    payload = CommandPayload(
        command_type="start_node",
        target_id="object_detector_node",
        args={"task_id": "t1"},
    )

    first = coordinator.accept(command_id="cmd-1", payload=payload)
    second = coordinator.accept(command_id="cmd-1", payload=payload)

    assert first.accepted is True
    assert second.accepted is True
    assert first.result_key == second.result_key


def test_same_command_id_different_payload_rejected_with_conflict() -> None:
    coordinator = CommandCoordinator()
    first_payload = CommandPayload(
        command_type="start_node",
        target_id="object_detector_node",
        args={"task_id": "t1"},
    )
    second_payload = CommandPayload(
        command_type="stop_node",
        target_id="object_detector_node",
        args={"task_id": "t1"},
    )

    coordinator.accept(command_id="cmd-2", payload=first_payload)
    result = coordinator.accept(command_id="cmd-2", payload=second_payload)

    assert result.accepted is False
    assert result.error_code == "CONFLICT"
