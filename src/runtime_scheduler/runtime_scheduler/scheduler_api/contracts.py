from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class TaskState(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class NodeActivation(str, Enum):
    REQUIRED = "required"
    OPTIONAL = "optional"


class Priority(str, Enum):
    HIGH = "high"
    NORMAL = "normal"


class CommandEventStatus(str, Enum):
    ACCEPTED = "accepted"
    IN_PROGRESS = "in_progress"
    PARTIALLY_APPLIED = "partially_applied"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class NodeRuntimeRef:
    node_id: str
    activation: NodeActivation
    priority: Priority | None = None
    constraints_ref: str | None = None


@dataclass(frozen=True, slots=True)
class EdgeRuntimeRef:
    edge_id: str
    activation: NodeActivation
    priority: Priority | None = None


@dataclass(frozen=True, slots=True)
class TaskSnapshot:
    task_id: str
    app_type: str
    task_type: str
    version: int
    timestamp_ms: int
    task_state: TaskState
    criticality: str
    node_refs: tuple[NodeRuntimeRef, ...] = field(default_factory=tuple)
    edge_refs: tuple[EdgeRuntimeRef, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.task_id:
            raise ValueError("task_id must be non-empty")
        if self.version <= 0:
            raise ValueError("version must be positive")
