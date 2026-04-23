from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
import math

from runtime_scheduler.task_catalog import CONTROLLER_TASK_IDS


def _controller_name_from_task_id(task_id: str) -> str:
    prefix = "controller-"
    if task_id.startswith(prefix):
        return task_id[len(prefix) :]
    return task_id


DEFAULT_CONTROLLER_NAMES: tuple[str, ...] = tuple(
    _controller_name_from_task_id(task_id) for task_id in CONTROLLER_TASK_IDS
)


def _percentile(values: Sequence[int], percentile: float) -> int:
    if not values:
        return 0
    sorted_values = sorted(values)
    rank = int(math.ceil((percentile / 100.0) * len(sorted_values))) - 1
    rank = max(0, min(rank, len(sorted_values) - 1))
    return int(sorted_values[rank])


def _to_int(value: object, default: int = 0) -> int:
    if value is None:
        return default
    return int(value)


def _to_bool(value: object) -> bool:
    return bool(value)


class ControllerCycleAggregator:
    """Aggregate controller cycle runtime records into one trace row per controller/window."""

    def __init__(self, controller_names: Sequence[str], period_target_us: int) -> None:
        self._controller_names = tuple(controller_names)
        self._period_target_us = int(period_target_us)

    def aggregate_window(
        self,
        *,
        experiment_id: str,
        window_id: str,
        timestamp_us: int,
        records: Sequence[Mapping[str, object]],
    ) -> list[dict[str, object]]:
        grouped: dict[str, list[Mapping[str, object]]] = defaultdict(list)
        for record in records:
            controller_name = str(record.get("controller_name", ""))
            if not controller_name:
                continue
            grouped[controller_name].append(record)

        ordered_controllers: list[str] = list(self._controller_names)
        for controller_name in sorted(grouped.keys()):
            if controller_name not in self._controller_names:
                ordered_controllers.append(controller_name)

        samples: list[dict[str, object]] = []
        for controller_name in ordered_controllers:
            rows = grouped.get(controller_name, [])
            exec_values = [_to_int(row.get("exec_time_mono_us")) for row in rows]
            period_values = [_to_int(row.get("cycle_period_sim_us")) for row in rows]

            period_target_us = self._period_target_us
            if rows and rows[0].get("period_target_us") is not None:
                period_target_us = _to_int(rows[0].get("period_target_us"), self._period_target_us)

            sample = {
                "schema_version": "v1",
                "experiment_id": experiment_id,
                "window_id": window_id,
                "timestamp_us": int(timestamp_us),
                "controller_name": controller_name,
                "period_target_us": period_target_us,
                "cycle_count": len(rows),
                "exec_mono_us_p50": _percentile(exec_values, 50),
                "exec_mono_us_p95": _percentile(exec_values, 95),
                "exec_mono_us_max": max(exec_values) if exec_values else 0,
                "period_sim_us_p50": _percentile(period_values, 50),
                "period_sim_us_p95": _percentile(period_values, 95),
                "period_sim_us_max": max(period_values) if period_values else 0,
                "deadline_miss_exec_count": sum(1 for row in rows if _to_bool(row.get("deadline_miss_exec"))),
                "late_start_sim_count": sum(1 for row in rows if _to_bool(row.get("late_start_sim"))),
                "late_finish_sim_count": sum(1 for row in rows if _to_bool(row.get("late_finish_sim"))),
                "late_arrival_count": sum(1 for row in rows if _to_bool(row.get("late_arrival"))),
            }
            samples.append(sample)

        return samples


def build_default_controller_cycle_records(
    *,
    window_start_us: int,
    controller_names: Sequence[str] = DEFAULT_CONTROLLER_NAMES,
    period_target_us: int,
) -> list[dict[str, object]]:
    """Fallback runtime records when no controller metrics source is available."""

    records: list[dict[str, object]] = []
    exec_time_us = max(1, period_target_us // 10)
    for controller_name in controller_names:
        cycle_start_sim_us = int(window_start_us)
        cycle_end_sim_us = int(window_start_us + period_target_us)
        cycle_start_mono_us = int(window_start_us)
        cycle_end_mono_us = int(cycle_start_mono_us + exec_time_us)
        records.append(
            {
                "controller_name": controller_name,
                "period_target_us": int(period_target_us),
                "cycle_start_sim_us": cycle_start_sim_us,
                "cycle_end_sim_us": cycle_end_sim_us,
                "cycle_period_sim_us": int(period_target_us),
                "cycle_start_mono_us": cycle_start_mono_us,
                "cycle_end_mono_us": cycle_end_mono_us,
                "exec_time_mono_us": exec_time_us,
                "deadline_miss_exec": exec_time_us > period_target_us,
                "late_start_sim": False,
                "late_finish_sim": False,
                "late_arrival": False,
            }
        )
    return records
