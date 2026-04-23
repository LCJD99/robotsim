from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any


class ExecutionAdapter:
    def __init__(
        self,
        cmd_vel_publisher: object,
        ensure: Callable[[list[str]], None],
        resume: Callable[[str], None],
        stop: Callable[[str], None],
        velocity_mapping: dict[str, tuple[float, float]],
    ) -> None:
        if "fallback" not in velocity_mapping:
            raise ValueError("velocity_mapping must include 'fallback'")
        self._cmd_vel_publisher = cmd_vel_publisher
        self._ensure = ensure
        self._resume = resume
        self._stop = stop
        self._velocity_mapping = velocity_mapping

    @staticmethod
    def _is_run_action(action: dict[str, Any]) -> bool:
        if "decision" in action:
            return action.get("decision") == "RUN"
        return action.get("action") == "RUN"

    @staticmethod
    def _normalize_lane(lane: str) -> str:
        if lane == "CRITICAL_LANE":
            return "critical"
        if lane == "CPU_LANE":
            return "high"
        return "fallback"

    def execute_window(
        self,
        task_actions: Sequence[dict[str, Any]],
        now_ms: int,
    ) -> dict[str, object]:
        del now_ms

        task_ids = [str(action["task_id"]) for action in task_actions]
        self._ensure(task_ids)

        run_actions = [action for action in task_actions if self._is_run_action(action)]
        worker_ops: list[dict[str, object]] = [{"op": "ensure", "task_ids": task_ids}]

        if run_actions:
            lane = self._normalize_lane(str(run_actions[0].get("lane", "fallback")))
            vx, wz = self._velocity_mapping.get(lane, self._velocity_mapping["fallback"])
            self._cmd_vel_publisher.publish_motion(vx, wz)
            cmd_vel = {"type": "motion", "vx": vx, "wz": wz}
        else:
            self._cmd_vel_publisher.publish_stop()
            cmd_vel = {"type": "stop", "vx": 0.0, "wz": 0.0}

        for action in task_actions:
            task_id = str(action["task_id"])
            if self._is_run_action(action):
                self._resume(task_id)
                worker_ops.append({"op": "resume", "task_id": task_id})
            else:
                self._stop(task_id)
                worker_ops.append({"op": "stop", "task_id": task_id})

        return {
            "success": True,
            "cmd_vel": cmd_vel,
            "worker_ops": worker_ops,
        }
