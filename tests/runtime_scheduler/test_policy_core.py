from runtime_scheduler.mode_trigger import HybridModeTrigger
from runtime_scheduler.policy_core import plan_critical_first_fifo


def test_policy_orders_hard_critical_before_elastic_fifo_remainder():
    tasks = [
        {"task_id": "a", "priority_class": "ELASTIC"},
        {"task_id": "b", "priority_class": "HARD_CRITICAL"},
        {"task_id": "c", "priority_class": "ELASTIC"},
        {"task_id": "d", "priority_class": "HARD_CRITICAL"},
    ]

    actions = plan_critical_first_fifo(tasks)

    assert [action["task_id"] for action in actions] == ["b", "d", "a", "c"]
    assert [action["lane"] for action in actions] == [
        "CRITICAL_LANE",
        "CRITICAL_LANE",
        "CPU_LANE",
        "CPU_LANE",
    ]
    assert [action["decision"] for action in actions] == ["RUN", "RUN", "RUN", "RUN"]


def test_hybrid_mode_trigger_applies_cooldown_after_runtime_raise():
    trigger = HybridModeTrigger(cooldown_windows=2)

    assert trigger.decide(window_index=10, runtime_raise=True, scheduler_requested="EMERGENCY") == "CONSERVATIVE"
    assert trigger.decide(window_index=11, runtime_raise=False, scheduler_requested="EMERGENCY") == "CONSERVATIVE"
    assert trigger.decide(window_index=12, runtime_raise=False, scheduler_requested="EMERGENCY") == "EMERGENCY"


def test_hybrid_mode_trigger_falls_back_to_normal_for_invalid_requested_mode():
    trigger = HybridModeTrigger(cooldown_windows=0)

    assert trigger.decide(window_index=1, runtime_raise=False, scheduler_requested="INVALID") == "NORMAL"
