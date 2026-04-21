from __future__ import annotations

from typing import Any

_CRITICAL_PRIORITY_CLASSES = {"HARD_CRITICAL", "SOFT_CRITICAL"}


def plan_critical_first_fifo(tasks: list[dict[str, Any]]) -> list[dict[str, str]]:
    critical_actions: list[dict[str, str]] = []
    cpu_actions: list[dict[str, str]] = []

    for task in tasks:
        action = {
            "task_id": str(task["task_id"]),
            "decision": "RUN",
            "lane": "CRITICAL_LANE"
            if task.get("priority_class") in _CRITICAL_PRIORITY_CLASSES
            else "CPU_LANE",
        }
        if action["lane"] == "CRITICAL_LANE":
            critical_actions.append(action)
        else:
            cpu_actions.append(action)

    return critical_actions + cpu_actions
