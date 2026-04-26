from __future__ import annotations

from runtime_scheduler.scheduler_api.contracts import (
    NodeActivation,
    NodeRuntimeRef,
    TaskSnapshot,
    TaskState,
)
from runtime_scheduler.scheduler_api.registry import NodeSpec, NumericBounds

CAMERA_INGEST_NODE_ID = "camera_ingest"
OBJECT_DETECTOR_NODE_ID = "object_detector"
CONTROLLER_BRIDGE_NODE_ID = "controller_bridge"


def build_fake_node_specs() -> tuple[NodeSpec, ...]:
    return (
        NodeSpec(
            node_id=CAMERA_INGEST_NODE_ID,
            cpu_quota=NumericBounds(min_value=0.1, max_value=1.0, default_value=0.3),
            max_concurrency=NumericBounds(min_value=1, max_value=8, default_value=2),
            core_always_on=False,
            default_priority="normal",
        ),
        NodeSpec(
            node_id=OBJECT_DETECTOR_NODE_ID,
            cpu_quota=NumericBounds(min_value=0.1, max_value=2.0, default_value=1.2),
            max_concurrency=NumericBounds(min_value=1, max_value=16, default_value=4),
            core_always_on=False,
            default_priority="normal",
        ),
        NodeSpec(
            node_id=CONTROLLER_BRIDGE_NODE_ID,
            cpu_quota=NumericBounds(min_value=0.1, max_value=1.0, default_value=0.5),
            max_concurrency=NumericBounds(min_value=1, max_value=4, default_value=1),
            core_always_on=True,
            default_priority="high",
        ),
    )


def build_demo_task_snapshot() -> TaskSnapshot:
    return TaskSnapshot(
        task_id="task-mvp-1",
        app_type="perception_recognition_app",
        task_type="recognize_objects",
        version=1,
        timestamp_ms=1_000,
        task_state=TaskState.RUNNING,
        criticality="critical",
        node_refs=(
            NodeRuntimeRef(node_id=OBJECT_DETECTOR_NODE_ID, activation=NodeActivation.REQUIRED),
            NodeRuntimeRef(node_id=CAMERA_INGEST_NODE_ID, activation=NodeActivation.OPTIONAL),
        ),
        edge_refs=(),
    )
