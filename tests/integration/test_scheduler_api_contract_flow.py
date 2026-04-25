from runtime_scheduler.scheduler_api.contracts import (
    NodeActivation,
    NodeRuntimeRef,
    Priority,
    TaskSnapshot,
    TaskState,
)
from runtime_scheduler.scheduler_api.merge_engine import merge_node_state
from runtime_scheduler.scheduler_api.registry import NodeSpec, NumericBounds


def test_completed_task_snapshot_does_not_keep_node_required() -> None:
    spec = NodeSpec(
        node_id="object_detector_node",
        core_always_on=False,
        default_priority=Priority.NORMAL,
        cpu_quota=NumericBounds(min_value=0.1, max_value=2.0),
        max_concurrency=NumericBounds(min_value=1, max_value=8),
    )
    completed = TaskSnapshot(
        task_id="task-1",
        app_type="perception_recognition_app",
        task_type="recognize_objects",
        version=1,
        timestamp_ms=1,
        task_state=TaskState.COMPLETED,
        criticality="critical",
        node_refs=(
            NodeRuntimeRef(
                node_id="object_detector_node",
                activation=NodeActivation.REQUIRED,
            ),
        ),
        edge_refs=(),
    )

    merged = merge_node_state(node_spec=spec, snapshots=(completed,))

    assert merged.activation != NodeActivation.REQUIRED
