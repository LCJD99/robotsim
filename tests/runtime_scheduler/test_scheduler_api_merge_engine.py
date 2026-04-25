from runtime_scheduler.scheduler_api.contracts import (
    NodeActivation,
    NodeRuntimeRef,
    Priority,
    TaskSnapshot,
    TaskState,
)
from runtime_scheduler.scheduler_api.merge_engine import merge_node_state
from runtime_scheduler.scheduler_api.registry import NodeSpec, NumericBounds


def _node_spec(*, core_always_on: bool = False) -> NodeSpec:
    return NodeSpec(
        node_id="object_detector_node",
        core_always_on=core_always_on,
        default_priority=Priority.NORMAL,
        cpu_quota=NumericBounds(min_value=0.1, max_value=2.0),
        max_concurrency=NumericBounds(min_value=1, max_value=8),
    )


def _snapshot(
    *,
    task_id: str,
    task_state: TaskState,
    criticality: str = "non_critical",
    node_refs: tuple[NodeRuntimeRef, ...] = (),
) -> TaskSnapshot:
    return TaskSnapshot(
        task_id=task_id,
        app_type="perception_recognition_app",
        task_type="recognize_objects",
        version=1,
        timestamp_ms=1,
        task_state=task_state,
        criticality=criticality,
        node_refs=node_refs,
        edge_refs=(),
    )


def test_core_always_on_forces_required_even_without_refs() -> None:
    state = merge_node_state(
        node_spec=_node_spec(core_always_on=True),
        snapshots=(_snapshot(task_id="task-1", task_state=TaskState.RUNNING),),
    )
    assert state.activation == NodeActivation.REQUIRED


def test_terminal_states_do_not_participate_in_merge() -> None:
    state = merge_node_state(
        node_spec=_node_spec(core_always_on=False),
        snapshots=(
            _snapshot(
                task_id="task-2",
                task_state=TaskState.COMPLETED,
                node_refs=(
                    NodeRuntimeRef(
                        node_id="object_detector_node",
                        activation=NodeActivation.REQUIRED,
                    ),
                ),
            ),
            _snapshot(task_id="task-3", task_state=TaskState.RUNNING),
        ),
    )
    assert state.activation != NodeActivation.REQUIRED


def test_activation_merge_required_over_optional_over_unused() -> None:
    state_optional = merge_node_state(
        node_spec=_node_spec(core_always_on=False),
        snapshots=(
            _snapshot(
                task_id="task-4",
                task_state=TaskState.PENDING,
                node_refs=(
                    NodeRuntimeRef(
                        node_id="object_detector_node",
                        activation=NodeActivation.OPTIONAL,
                    ),
                ),
            ),
            _snapshot(task_id="task-5", task_state=TaskState.RUNNING),
        ),
    )
    assert state_optional.activation == NodeActivation.OPTIONAL

    state_required = merge_node_state(
        node_spec=_node_spec(core_always_on=False),
        snapshots=(
            _snapshot(
                task_id="task-6",
                task_state=TaskState.RUNNING,
                node_refs=(
                    NodeRuntimeRef(
                        node_id="object_detector_node",
                        activation=NodeActivation.OPTIONAL,
                    ),
                ),
            ),
            _snapshot(
                task_id="task-7",
                task_state=TaskState.PENDING,
                node_refs=(
                    NodeRuntimeRef(
                        node_id="object_detector_node",
                        activation=NodeActivation.REQUIRED,
                    ),
                ),
            ),
        ),
    )
    assert state_required.activation == NodeActivation.REQUIRED


def test_priority_merge_high_over_normal_for_active_tasks() -> None:
    state = merge_node_state(
        node_spec=_node_spec(core_always_on=False),
        snapshots=(
            _snapshot(
                task_id="task-8",
                task_state=TaskState.RUNNING,
                node_refs=(
                    NodeRuntimeRef(
                        node_id="object_detector_node",
                        activation=NodeActivation.REQUIRED,
                        priority=Priority.NORMAL,
                    ),
                ),
            ),
            _snapshot(
                task_id="task-9",
                task_state=TaskState.PENDING,
                node_refs=(
                    NodeRuntimeRef(
                        node_id="object_detector_node",
                        activation=NodeActivation.OPTIONAL,
                        priority=Priority.HIGH,
                    ),
                ),
            ),
        ),
    )
    assert state.priority == Priority.HIGH
