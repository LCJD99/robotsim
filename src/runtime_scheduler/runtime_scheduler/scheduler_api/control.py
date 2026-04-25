from __future__ import annotations

from runtime_scheduler.scheduler_api.errors import ApiError
from runtime_scheduler.scheduler_api.registry import NodeSpec


def validate_sync_command(node_spec: NodeSpec, field_name: str, value: float) -> None:
    if field_name == "cpu_quota":
        bounds = node_spec.cpu_quota
    elif field_name == "max_concurrency":
        bounds = node_spec.max_concurrency
    else:
        return

    if not bounds.contains(value):
        raise ApiError(
            code="INVALID_ARG",
            message=f"{field_name} is out of bounds",
            details={
                "reason": "bound_violation",
                "field": field_name,
                "min": bounds.min_value,
                "max": bounds.max_value,
                "value": value,
            },
        )
