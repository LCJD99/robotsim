from __future__ import annotations

from runtime_scheduler.policy_core import plan_critical_first_fifo

SCHEDULER_VERSION = "v1"
POLICY_HASH = "critical_first_fifo"


def run_single_window(window_id: str, timestamp_us: int, tasks: list[dict]) -> tuple[dict, dict, dict]:
    task_actions = plan_critical_first_fifo(tasks)
    plan_id = f"plan-{window_id}"
    outcome_id = f"outcome-{window_id}"

    observation = {
        "schema_version": "v1",
        "window_id": window_id,
        "timestamp_us": timestamp_us,
        "scheduler_version": SCHEDULER_VERSION,
        "policy_hash": POLICY_HASH,
        "task_count": len(tasks),
    }
    plan = {
        "schema_version": "v1",
        "plan_id": plan_id,
        "window_id": window_id,
        "generated_at_us": timestamp_us,
        "scheduler_version": SCHEDULER_VERSION,
        "policy_hash": POLICY_HASH,
        "task_actions": task_actions,
        "task_count": len(task_actions),
    }
    outcome = {
        "schema_version": "v1",
        "outcome_id": outcome_id,
        "window_id": window_id,
        "plan_id": plan_id,
        "scheduler_version": SCHEDULER_VERSION,
        "policy_hash": POLICY_HASH,
        "task_count": len(task_actions),
        "completed_task_ids": [action["task_id"] for action in task_actions],
    }

    return observation, plan, outcome
