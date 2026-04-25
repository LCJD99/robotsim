from runtime_scheduler.scheduler_api.control import validate_sync_command
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
