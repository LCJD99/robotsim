from __future__ import annotations

from typing import Final

CONTROLLER_TASK_TYPE: Final[str] = "ROS_CONTROLLER_CYCLE"
CONTROLLER_TASK_SOURCE: Final[str] = "controller_runtime"
CONTROLLER_ARRIVAL_SOURCE: Final[str] = "periodic_controller"
CONTROLLER_GENERATOR_SEED: Final[int] = -1
CONTROLLER_LAMBDA_PER_SEC: Final[float] = 0.0
CONTROLLER_PRIORITY_CLASS: Final[str] = "HARD_CRITICAL"

CONTROLLER_TASK_IDS: Final[tuple[str, str]] = (
    "controller-joint_state_broadcaster",
    "controller-diff_drive_controller",
)


def build_local_tool_task(arrival: dict[str, object]) -> dict[str, object]:
    return {
        "task_id": arrival["task_id"],
        "priority_class": "ELASTIC",
    }


def build_local_tool_task_event(
    experiment_id: str,
    arrival: dict[str, object],
) -> dict[str, object]:
    task_id = str(arrival["task_id"])
    window_id = str(arrival["window_id"])
    return {
        "schema_version": "v1",
        "experiment_id": experiment_id,
        "event_id": f"evt-{window_id}-{task_id}",
        "event_type": "TASK_ARRIVAL",
        "timestamp_us": arrival["timestamp_us"],
        "window_id": arrival["window_id"],
        "task_id": arrival["task_id"],
        "request_id": arrival["request_id"],
        "task_type": "LOCAL_TOOL",
        "source": "generator",
        "arrival_source": arrival["arrival_source"],
        "generator_seed": arrival["generator_seed"],
        "lambda_per_sec": arrival["lambda_per_sec"],
    }


def build_controller_periodic_tasks(window_id: str, timestamp_us: int) -> list[dict[str, object]]:
    del window_id, timestamp_us
    return [
        {
            "task_id": task_id,
            "priority_class": CONTROLLER_PRIORITY_CLASS,
        }
        for task_id in CONTROLLER_TASK_IDS
    ]


def build_controller_task_events(
    experiment_id: str,
    window_id: str,
    timestamp_us: int,
) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    for task_id in CONTROLLER_TASK_IDS:
        events.append(
            {
                "schema_version": "v1",
                "experiment_id": experiment_id,
                "event_id": f"evt-{window_id}-{task_id}",
                "event_type": "TASK_ARRIVAL",
                "timestamp_us": timestamp_us,
                "window_id": window_id,
                "task_id": task_id,
                "request_id": f"request-{window_id}-{task_id}",
                "task_type": CONTROLLER_TASK_TYPE,
                "source": CONTROLLER_TASK_SOURCE,
                "arrival_source": CONTROLLER_ARRIVAL_SOURCE,
                "generator_seed": CONTROLLER_GENERATOR_SEED,
                "lambda_per_sec": CONTROLLER_LAMBDA_PER_SEC,
            }
        )
    return events
