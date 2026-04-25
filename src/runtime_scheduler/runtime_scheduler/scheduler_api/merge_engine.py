from __future__ import annotations

from dataclasses import dataclass

from runtime_scheduler.scheduler_api.contracts import (
    NodeActivation,
    Priority,
    TaskSnapshot,
    TaskState,
)
from runtime_scheduler.scheduler_api.registry import NodeSpec

ACTIVE_STATES = {TaskState.PENDING, TaskState.RUNNING}


@dataclass(frozen=True, slots=True)
class EffectiveNodeState:
    activation: NodeActivation
    priority: Priority


def _is_active(snapshot: TaskSnapshot) -> bool:
    return snapshot.task_state in ACTIVE_STATES


def _normalize_priority(value: Priority | str | None) -> Priority:
    if value == Priority.HIGH or value == Priority.HIGH.value:
        return Priority.HIGH
    return Priority.NORMAL


def _priority_from_snapshot(snapshot: TaskSnapshot) -> Priority:
    if snapshot.criticality == "critical":
        return Priority.HIGH
    return Priority.NORMAL


def merge_node_state(node_spec: NodeSpec, snapshots: tuple[TaskSnapshot, ...]) -> EffectiveNodeState:
    effective_priority = _normalize_priority(node_spec.default_priority)
    if node_spec.core_always_on:
        return EffectiveNodeState(
            activation=NodeActivation.REQUIRED,
            priority=effective_priority,
        )

    has_required = False
    has_optional = False

    for snapshot in snapshots:
        if not _is_active(snapshot):
            continue
        for ref in snapshot.node_refs:
            if ref.node_id != node_spec.node_id:
                continue
            if ref.activation == NodeActivation.REQUIRED:
                has_required = True
            elif ref.activation == NodeActivation.OPTIONAL:
                has_optional = True

            candidate_priority = ref.priority or _priority_from_snapshot(snapshot)
            if _normalize_priority(candidate_priority) == Priority.HIGH:
                effective_priority = Priority.HIGH

    if has_required:
        effective_activation = NodeActivation.REQUIRED
    elif has_optional:
        effective_activation = NodeActivation.OPTIONAL
    else:
        # "unused" is represented as OPTIONAL in the v1 API surface.
        effective_activation = NodeActivation.OPTIONAL

    return EffectiveNodeState(activation=effective_activation, priority=effective_priority)
