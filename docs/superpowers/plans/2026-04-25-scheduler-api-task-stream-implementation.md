# Scheduler API and Task Stream Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement protocol-agnostic scheduler contracts and merge/control primitives for task-stream-driven node scheduling with registry guardrails.

**Architecture:** Add a focused `scheduler_api` module under `runtime_scheduler` with three layers: contracts (models/enums), merge engine (active-task + core-always-on semantics), and control coordinator (bounds validation + idempotent command handling). Keep transport-neutral interfaces so gRPC/REST adapters can be added later without changing core logic.

**Tech Stack:** Python 3.10+, dataclasses, typing Protocol, pytest

---

## File Structure

- Create: `src/runtime_scheduler/runtime_scheduler/scheduler_api/__init__.py`
- Create: `src/runtime_scheduler/runtime_scheduler/scheduler_api/contracts.py`
- Create: `src/runtime_scheduler/runtime_scheduler/scheduler_api/registry.py`
- Create: `src/runtime_scheduler/runtime_scheduler/scheduler_api/merge_engine.py`
- Create: `src/runtime_scheduler/runtime_scheduler/scheduler_api/observation.py`
- Create: `src/runtime_scheduler/runtime_scheduler/scheduler_api/control.py`
- Create: `src/runtime_scheduler/runtime_scheduler/scheduler_api/errors.py`
- Create: `tests/runtime_scheduler/test_scheduler_api_contracts.py`
- Create: `tests/runtime_scheduler/test_scheduler_api_merge_engine.py`
- Create: `tests/runtime_scheduler/test_scheduler_api_observation.py`
- Create: `tests/runtime_scheduler/test_scheduler_api_control.py`
- Modify: `src/runtime_scheduler/runtime_scheduler/__init__.py`

Responsibilities:
- `contracts.py`: task/node/edge/command event contracts and enums.
- `registry.py`: registry spec models (`NodeSpec`, `EdgeSpec`, `bounds`) and query protocol.
- `merge_engine.py`: active-task filtering and node/edge activation/priority merge.
- `observation.py`: snapshot ingestion state (`latest version`) and stale snapshot event emission.
- `control.py`: sync/async command handling, bounds validation, and command-id idempotency.
- `errors.py`: common error code model and reusable exception types.

### Task 1: Contract Models and Enums

**Files:**
- Create: `src/runtime_scheduler/runtime_scheduler/scheduler_api/contracts.py`
- Create: `tests/runtime_scheduler/test_scheduler_api_contracts.py`
- Modify: `src/runtime_scheduler/runtime_scheduler/scheduler_api/__init__.py`

- [ ] **Step 1: Write the failing tests for snapshot and command contracts**

```python
# tests/runtime_scheduler/test_scheduler_api_contracts.py
from runtime_scheduler.scheduler_api.contracts import (
    CommandEventStatus,
    NodeActivation,
    TaskSnapshot,
    TaskState,
)


def test_task_snapshot_requires_task_id_and_positive_version() -> None:
    try:
        TaskSnapshot(
            task_id="",
            app_type="perception_recognition_app",
            task_type="recognize_objects",
            version=0,
            timestamp_ms=123,
            task_state=TaskState.PENDING,
            criticality="critical",
            node_refs=[],
            edge_refs=[],
        )
    except ValueError as exc:
        assert "task_id" in str(exc) or "version" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_command_event_status_enum_contains_required_states() -> None:
    assert CommandEventStatus.ACCEPTED.value == "accepted"
    assert CommandEventStatus.PARTIALLY_APPLIED.value == "partially_applied"


def test_node_activation_has_required_and_optional_only() -> None:
    values = {member.value for member in NodeActivation}
    assert values == {"required", "optional"}
```

- [ ] **Step 2: Run tests to verify failure**

Run: `python3 -m pytest -q tests/runtime_scheduler/test_scheduler_api_contracts.py`  
Expected: FAIL with `ModuleNotFoundError: No module named 'runtime_scheduler.scheduler_api'`

- [ ] **Step 3: Implement contract dataclasses and enums**

```python
# src/runtime_scheduler/runtime_scheduler/scheduler_api/contracts.py
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
```

- [ ] **Step 4: Export module and rerun tests**

```python
# src/runtime_scheduler/runtime_scheduler/scheduler_api/__init__.py
from .contracts import (
    CommandEventStatus,
    EdgeRuntimeRef,
    NodeActivation,
    NodeRuntimeRef,
    Priority,
    TaskSnapshot,
    TaskState,
)
```

Run: `python3 -m pytest -q tests/runtime_scheduler/test_scheduler_api_contracts.py`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/runtime_scheduler/runtime_scheduler/scheduler_api/__init__.py \
  src/runtime_scheduler/runtime_scheduler/scheduler_api/contracts.py \
  tests/runtime_scheduler/test_scheduler_api_contracts.py
git commit -m "feat: add scheduler api contract models"
```

### Task 2: Registry Specs and Bounds Guardrails

**Files:**
- Create: `src/runtime_scheduler/runtime_scheduler/scheduler_api/registry.py`
- Create: `src/runtime_scheduler/runtime_scheduler/scheduler_api/errors.py`
- Create: `tests/runtime_scheduler/test_scheduler_api_control.py`

- [ ] **Step 1: Write failing tests for bounds and defaults from registry**

```python
# tests/runtime_scheduler/test_scheduler_api_control.py
from runtime_scheduler.scheduler_api.control import validate_sync_command
from runtime_scheduler.scheduler_api.registry import EdgeSpec, NodeSpec, NumericBounds


def test_validate_sync_command_rejects_out_of_bounds_cpu_quota() -> None:
    node = NodeSpec(
        node_id="detector",
        core_always_on=False,
        default_priority="normal",
        cpu_quota=NumericBounds(min_value=10, max_value=80, default_value=50),
        max_concurrency=NumericBounds(min_value=1, max_value=8, default_value=2),
        model_variants=("base", "fast"),
        default_model_variant="base",
    )
    err = validate_sync_command(node_spec=node, field_name="cpu_quota", value=95)
    assert err is not None
    assert err.code == "INVALID_ARG"
    assert err.details["reason"] == "bound_violation"
```

- [ ] **Step 2: Run test to verify failure**

Run: `python3 -m pytest -q tests/runtime_scheduler/test_scheduler_api_control.py::test_validate_sync_command_rejects_out_of_bounds_cpu_quota`  
Expected: FAIL with import error for `runtime_scheduler.scheduler_api.control`

- [ ] **Step 3: Add error model and registry spec models**

```python
# src/runtime_scheduler/runtime_scheduler/scheduler_api/errors.py
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class ApiError:
    code: str
    message: str
    details: dict[str, object] = field(default_factory=dict)
```

```python
# src/runtime_scheduler/runtime_scheduler/scheduler_api/registry.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class NumericBounds:
    min_value: int
    max_value: int
    default_value: int


@dataclass(frozen=True, slots=True)
class NodeSpec:
    node_id: str
    core_always_on: bool
    default_priority: str
    cpu_quota: NumericBounds
    max_concurrency: NumericBounds
    model_variants: tuple[str, ...]
    default_model_variant: str


@dataclass(frozen=True, slots=True)
class EdgeSpec:
    edge_id: str
    src_node_id: str
    dst_node_id: str
    topic_rate: NumericBounds
    queue_depth: NumericBounds
    drop_policies: tuple[str, ...]
    default_drop_policy: str


class RegistryClient(Protocol):
    def get_node_spec(self, node_id: str) -> NodeSpec: ...

    def get_edge_spec(self, edge_id: str) -> EdgeSpec: ...
```

- [ ] **Step 4: Add minimal bounds validator in control module and run tests**

```python
# src/runtime_scheduler/runtime_scheduler/scheduler_api/control.py
from __future__ import annotations

from runtime_scheduler.scheduler_api.errors import ApiError
from runtime_scheduler.scheduler_api.registry import NodeSpec


def validate_sync_command(node_spec: NodeSpec, field_name: str, value: int) -> ApiError | None:
    if field_name == "cpu_quota":
        bounds = node_spec.cpu_quota
    elif field_name == "max_concurrency":
        bounds = node_spec.max_concurrency
    else:
        return ApiError(code="INVALID_ARG", message="unknown field", details={"field": field_name})

    if not (bounds.min_value <= value <= bounds.max_value):
        return ApiError(
            code="INVALID_ARG",
            message="value out of bounds",
            details={
                "reason": "bound_violation",
                "field": field_name,
                "min": bounds.min_value,
                "max": bounds.max_value,
                "value": value,
            },
        )
    return None
```

Run: `python3 -m pytest -q tests/runtime_scheduler/test_scheduler_api_control.py::test_validate_sync_command_rejects_out_of_bounds_cpu_quota`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/runtime_scheduler/runtime_scheduler/scheduler_api/errors.py \
  src/runtime_scheduler/runtime_scheduler/scheduler_api/registry.py \
  src/runtime_scheduler/runtime_scheduler/scheduler_api/control.py \
  tests/runtime_scheduler/test_scheduler_api_control.py
git commit -m "feat: add registry guardrail models and bounds validation"
```

### Task 3: Merge Engine (Active Task + Core Always On)

**Files:**
- Create: `src/runtime_scheduler/runtime_scheduler/scheduler_api/merge_engine.py`
- Create: `tests/runtime_scheduler/test_scheduler_api_merge_engine.py`

- [ ] **Step 1: Write failing tests for activation and priority merge semantics**

```python
# tests/runtime_scheduler/test_scheduler_api_merge_engine.py
from runtime_scheduler.scheduler_api.contracts import NodeActivation, NodeRuntimeRef, Priority, TaskSnapshot, TaskState
from runtime_scheduler.scheduler_api.merge_engine import merge_node_state
from runtime_scheduler.scheduler_api.registry import NodeSpec, NumericBounds


def _node_spec(core: bool) -> NodeSpec:
    return NodeSpec(
        node_id="object_detector_node",
        core_always_on=core,
        default_priority="normal",
        cpu_quota=NumericBounds(min_value=10, max_value=80, default_value=50),
        max_concurrency=NumericBounds(min_value=1, max_value=8, default_value=2),
        model_variants=("base",),
        default_model_variant="base",
    )


def test_core_always_on_forces_required_even_without_refs() -> None:
    snap = TaskSnapshot(
        task_id="task-1",
        app_type="perception_recognition_app",
        task_type="recognize_objects",
        version=1,
        timestamp_ms=1,
        task_state=TaskState.RUNNING,
        criticality="non_critical",
        node_refs=(),
        edge_refs=(),
    )
    state = merge_node_state(node_spec=_node_spec(core=True), snapshots=(snap,))
    assert state.activation == NodeActivation.REQUIRED


def test_terminal_tasks_do_not_participate_in_merge() -> None:
    snap = TaskSnapshot(
        task_id="task-2",
        app_type="perception_recognition_app",
        task_type="recognize_objects",
        version=1,
        timestamp_ms=1,
        task_state=TaskState.COMPLETED,
        criticality="critical",
        node_refs=(NodeRuntimeRef(node_id="object_detector_node", activation=NodeActivation.REQUIRED),),
        edge_refs=(),
    )
    state = merge_node_state(node_spec=_node_spec(core=False), snapshots=(snap,))
    assert state.activation != NodeActivation.REQUIRED


def test_priority_merges_high_over_normal_for_active_tasks() -> None:
    running = TaskSnapshot(
        task_id="task-3",
        app_type="perception_recognition_app",
        task_type="recognize_objects",
        version=1,
        timestamp_ms=1,
        task_state=TaskState.RUNNING,
        criticality="non_critical",
        node_refs=(NodeRuntimeRef(node_id="object_detector_node", activation=NodeActivation.REQUIRED, priority=Priority.NORMAL),),
        edge_refs=(),
    )
    pending = TaskSnapshot(
        task_id="task-4",
        app_type="perception_recognition_app",
        task_type="recognize_objects",
        version=1,
        timestamp_ms=2,
        task_state=TaskState.PENDING,
        criticality="critical",
        node_refs=(NodeRuntimeRef(node_id="object_detector_node", activation=NodeActivation.OPTIONAL, priority=Priority.HIGH),),
        edge_refs=(),
    )
    state = merge_node_state(node_spec=_node_spec(core=False), snapshots=(running, pending))
    assert state.priority == Priority.HIGH
```

- [ ] **Step 2: Run test to verify failure**

Run: `python3 -m pytest -q tests/runtime_scheduler/test_scheduler_api_merge_engine.py`  
Expected: FAIL with import error for `runtime_scheduler.scheduler_api.merge_engine`

- [ ] **Step 3: Implement merge engine**

```python
# src/runtime_scheduler/runtime_scheduler/scheduler_api/merge_engine.py
from __future__ import annotations

from dataclasses import dataclass

from runtime_scheduler.scheduler_api.contracts import NodeActivation, Priority, TaskSnapshot, TaskState
from runtime_scheduler.scheduler_api.registry import NodeSpec


ACTIVE_STATES = {TaskState.PENDING, TaskState.RUNNING}


@dataclass(frozen=True, slots=True)
class EffectiveNodeState:
    activation: NodeActivation
    priority: Priority


def _is_active(snapshot: TaskSnapshot) -> bool:
    return snapshot.task_state in ACTIVE_STATES


def merge_node_state(node_spec: NodeSpec, snapshots: tuple[TaskSnapshot, ...]) -> EffectiveNodeState:
    if node_spec.core_always_on:
        return EffectiveNodeState(activation=NodeActivation.REQUIRED, priority=Priority.HIGH)

    activation_rank = {"unused": 0, NodeActivation.OPTIONAL: 1, NodeActivation.REQUIRED: 2}
    priority_rank = {Priority.NORMAL: 0, Priority.HIGH: 1}

    effective_activation: NodeActivation | None = None
    effective_priority = Priority.HIGH if node_spec.default_priority == "high" else Priority.NORMAL

    for snap in snapshots:
        if not _is_active(snap):
            continue
        for ref in snap.node_refs:
            if ref.node_id != node_spec.node_id:
                continue
            if effective_activation is None or activation_rank[ref.activation] > activation_rank[effective_activation]:
                effective_activation = ref.activation
            candidate_priority = ref.priority
            if candidate_priority is None:
                candidate_priority = Priority.HIGH if snap.criticality == "critical" else Priority.NORMAL
            if priority_rank[candidate_priority] > priority_rank[effective_priority]:
                effective_priority = candidate_priority

    if effective_activation is None:
        effective_activation = NodeActivation.OPTIONAL

    return EffectiveNodeState(activation=effective_activation, priority=effective_priority)
```

- [ ] **Step 4: Correct unused semantics and rerun tests**

```python
# replace tail in merge_node_state
if effective_activation is None:
    # Omitted from all active snapshots => unused; represent as OPTIONAL in v1 control layer
    effective_activation = NodeActivation.OPTIONAL
```

Run: `python3 -m pytest -q tests/runtime_scheduler/test_scheduler_api_merge_engine.py`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/runtime_scheduler/runtime_scheduler/scheduler_api/merge_engine.py \
  tests/runtime_scheduler/test_scheduler_api_merge_engine.py
git commit -m "feat: add active-task merge semantics for scheduler api"
```

### Task 4: Observation Snapshot Processor and Stale Detection

**Files:**
- Create: `src/runtime_scheduler/runtime_scheduler/scheduler_api/observation.py`
- Create: `tests/runtime_scheduler/test_scheduler_api_observation.py`

- [ ] **Step 1: Write failing tests for version acceptance and stale events**

```python
# tests/runtime_scheduler/test_scheduler_api_observation.py
from runtime_scheduler.scheduler_api.contracts import TaskSnapshot, TaskState
from runtime_scheduler.scheduler_api.observation import ObservationProcessor


def _snapshot(version: int) -> TaskSnapshot:
    return TaskSnapshot(
        task_id="task-1",
        app_type="perception_recognition_app",
        task_type="recognize_objects",
        version=version,
        timestamp_ms=version,
        task_state=TaskState.RUNNING,
        criticality="non_critical",
        node_refs=(),
        edge_refs=(),
    )


def test_accepts_monotonic_increasing_versions() -> None:
    processor = ObservationProcessor()
    assert processor.push_task_snapshot(_snapshot(1)).accepted is True
    assert processor.push_task_snapshot(_snapshot(3)).accepted is True


def test_rejects_duplicate_or_stale_version() -> None:
    processor = ObservationProcessor()
    processor.push_task_snapshot(_snapshot(2))
    result = processor.push_task_snapshot(_snapshot(2))
    assert result.accepted is False
    assert result.event_type == "stale_snapshot"
```

- [ ] **Step 2: Run test to verify failure**

Run: `python3 -m pytest -q tests/runtime_scheduler/test_scheduler_api_observation.py`  
Expected: FAIL with import error for `runtime_scheduler.scheduler_api.observation`

- [ ] **Step 3: Implement observation processor**

```python
# src/runtime_scheduler/runtime_scheduler/scheduler_api/observation.py
from __future__ import annotations

from dataclasses import dataclass

from runtime_scheduler.scheduler_api.contracts import TaskSnapshot


@dataclass(frozen=True, slots=True)
class SnapshotIngestResult:
    accepted: bool
    event_type: str | None = None


class ObservationProcessor:
    def __init__(self) -> None:
        self._latest_versions: dict[str, int] = {}

    def push_task_snapshot(self, snapshot: TaskSnapshot) -> SnapshotIngestResult:
        latest = self._latest_versions.get(snapshot.task_id)
        if latest is not None and snapshot.version <= latest:
            return SnapshotIngestResult(accepted=False, event_type="stale_snapshot")
        self._latest_versions[snapshot.task_id] = snapshot.version
        return SnapshotIngestResult(accepted=True, event_type=None)
```

- [ ] **Step 4: Run tests to verify pass**

Run: `python3 -m pytest -q tests/runtime_scheduler/test_scheduler_api_observation.py`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/runtime_scheduler/runtime_scheduler/scheduler_api/observation.py \
  tests/runtime_scheduler/test_scheduler_api_observation.py
git commit -m "feat: add snapshot observation processor with stale detection"
```

### Task 5: Idempotent Command Handling and Async Status Tracking

**Files:**
- Modify: `src/runtime_scheduler/runtime_scheduler/scheduler_api/control.py`
- Modify: `tests/runtime_scheduler/test_scheduler_api_control.py`

- [ ] **Step 1: Add failing tests for command_id idempotency**

```python
# add to tests/runtime_scheduler/test_scheduler_api_control.py
from runtime_scheduler.scheduler_api.control import CommandCoordinator, CommandPayload


def test_same_command_id_same_payload_returns_same_result() -> None:
    coordinator = CommandCoordinator()
    payload = CommandPayload(command_type="start_node", target_id="object_detector_node", args={"task_id": "t1"})

    first = coordinator.accept(command_id="cmd-1", payload=payload)
    second = coordinator.accept(command_id="cmd-1", payload=payload)

    assert first.accepted is True
    assert second.accepted is True
    assert first.result_key == second.result_key


def test_same_command_id_different_payload_rejected() -> None:
    coordinator = CommandCoordinator()
    one = CommandPayload(command_type="start_node", target_id="object_detector_node", args={"task_id": "t1"})
    two = CommandPayload(command_type="stop_node", target_id="object_detector_node", args={"task_id": "t1"})

    coordinator.accept(command_id="cmd-2", payload=one)
    result = coordinator.accept(command_id="cmd-2", payload=two)

    assert result.accepted is False
    assert result.error_code == "CONFLICT"
```

- [ ] **Step 2: Run tests to verify failure**

Run: `python3 -m pytest -q tests/runtime_scheduler/test_scheduler_api_control.py -k command_id`  
Expected: FAIL with missing `CommandCoordinator`

- [ ] **Step 3: Implement command coordinator in control module**

```python
# add to src/runtime_scheduler/runtime_scheduler/scheduler_api/control.py
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json


@dataclass(frozen=True, slots=True)
class CommandPayload:
    command_type: str
    target_id: str
    args: dict[str, object]


@dataclass(frozen=True, slots=True)
class CommandAcceptResult:
    accepted: bool
    result_key: str | None = None
    error_code: str | None = None


class CommandCoordinator:
    def __init__(self) -> None:
        self._seen: dict[str, str] = {}

    @staticmethod
    def _digest(payload: CommandPayload) -> str:
        serialized = json.dumps(
            {
                "command_type": payload.command_type,
                "target_id": payload.target_id,
                "args": payload.args,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return sha256(serialized.encode("utf-8")).hexdigest()

    def accept(self, command_id: str, payload: CommandPayload) -> CommandAcceptResult:
        digest = self._digest(payload)
        existing = self._seen.get(command_id)
        if existing is None:
            self._seen[command_id] = digest
            return CommandAcceptResult(accepted=True, result_key=digest)
        if existing != digest:
            return CommandAcceptResult(accepted=False, error_code="CONFLICT")
        return CommandAcceptResult(accepted=True, result_key=existing)
```

- [ ] **Step 4: Run targeted and full scheduler_api tests**

Run: `python3 -m pytest -q tests/runtime_scheduler/test_scheduler_api_control.py -k command_id`  
Expected: PASS

Run: `python3 -m pytest -q tests/runtime_scheduler/test_scheduler_api_contracts.py tests/runtime_scheduler/test_scheduler_api_merge_engine.py tests/runtime_scheduler/test_scheduler_api_observation.py tests/runtime_scheduler/test_scheduler_api_control.py`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/runtime_scheduler/runtime_scheduler/scheduler_api/control.py \
  tests/runtime_scheduler/test_scheduler_api_control.py
git commit -m "feat: enforce command-id idempotency in scheduler control api"
```

### Task 6: Integration Contract for Merge-to-Control Decision Guard

**Files:**
- Create: `tests/integration/test_scheduler_api_contract_flow.py`

- [ ] **Step 1: Write failing integration contract**

```python
# tests/integration/test_scheduler_api_contract_flow.py
from runtime_scheduler.scheduler_api.contracts import NodeActivation, NodeRuntimeRef, TaskSnapshot, TaskState
from runtime_scheduler.scheduler_api.merge_engine import merge_node_state
from runtime_scheduler.scheduler_api.registry import NodeSpec, NumericBounds


def test_completed_task_snapshot_does_not_keep_node_required() -> None:
    spec = NodeSpec(
        node_id="object_detector_node",
        core_always_on=False,
        default_priority="normal",
        cpu_quota=NumericBounds(min_value=10, max_value=80, default_value=50),
        max_concurrency=NumericBounds(min_value=1, max_value=8, default_value=2),
        model_variants=("base",),
        default_model_variant="base",
    )
    completed = TaskSnapshot(
        task_id="task-1",
        app_type="perception_recognition_app",
        task_type="recognize_objects",
        version=2,
        timestamp_ms=2,
        task_state=TaskState.COMPLETED,
        criticality="critical",
        node_refs=(NodeRuntimeRef(node_id="object_detector_node", activation=NodeActivation.REQUIRED),),
        edge_refs=(),
    )

    merged = merge_node_state(node_spec=spec, snapshots=(completed,))

    assert merged.activation != NodeActivation.REQUIRED
```

- [ ] **Step 2: Run integration test to verify failure first (if behavior not implemented yet)**

Run: `python3 -m pytest -q tests/integration/test_scheduler_api_contract_flow.py`  
Expected: FAIL initially if terminal filtering regresses; PASS after merge engine is in place.

- [ ] **Step 3: Ensure behavior is wired and stable (no code if already green)**

```python
# no code change required when Task 3 implementation is complete
# this step is verification-only to protect against regressions
```

- [ ] **Step 4: Run focused regression set**

Run: `python3 -m pytest -q tests/runtime_scheduler/test_scheduler_api_merge_engine.py tests/integration/test_scheduler_api_contract_flow.py`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/integration/test_scheduler_api_contract_flow.py
git commit -m "test: add integration contract for active-task merge behavior"
```

## Final Verification

- [ ] Run scheduler API test set:

Run:
`python3 -m pytest -q tests/runtime_scheduler/test_scheduler_api_contracts.py tests/runtime_scheduler/test_scheduler_api_merge_engine.py tests/runtime_scheduler/test_scheduler_api_observation.py tests/runtime_scheduler/test_scheduler_api_control.py tests/integration/test_scheduler_api_contract_flow.py`

Expected:
- All tests PASS

- [ ] Run full suite smoke before merge:

Run:
`python3 -m pytest -q`

Expected:
- No regressions in existing modules

## Spec Coverage Check

- Observation API snapshot full-state + stale drop event: covered by Task 1 and Task 4.
- Active vs terminal merge participation: covered by Task 3 and Task 6.
- `core_always_on` forcing required activation: covered by Task 3.
- Priority merge (`high > normal`) and task criticality defaults: covered by Task 3.
- Control bounds guardrails from registry defaults/bounds: covered by Task 2.
- Command idempotency keyed only by `command_id`: covered by Task 5.
- Transport-neutral API core: enforced by module design (no network framework dependency).

## Placeholder and Consistency Check

- No `TODO`/`TBD` placeholders in actionable steps.
- All command and type names are consistent across tasks:
  - `TaskSnapshot`, `NodeRuntimeRef`, `NodeSpec`, `merge_node_state`, `CommandCoordinator`.
- Commit sequence keeps each change logically isolated and reviewable.
