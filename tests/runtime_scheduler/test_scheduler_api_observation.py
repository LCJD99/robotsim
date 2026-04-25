from runtime_scheduler.scheduler_api.contracts import TaskSnapshot, TaskState
from runtime_scheduler.scheduler_api.observation import ObservationProcessor


def _snapshot(*, task_id: str = "task-1", version: int) -> TaskSnapshot:
    return TaskSnapshot(
        task_id=task_id,
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
    assert processor.push_task_snapshot(_snapshot(version=1)).accepted is True
    assert processor.push_task_snapshot(_snapshot(version=3)).accepted is True


def test_rejects_duplicate_or_stale_version() -> None:
    processor = ObservationProcessor()
    processor.push_task_snapshot(_snapshot(version=2))

    duplicate = processor.push_task_snapshot(_snapshot(version=2))
    assert duplicate.accepted is False
    assert duplicate.event_type == "stale_snapshot"

    stale = processor.push_task_snapshot(_snapshot(version=1))
    assert stale.accepted is False
    assert stale.event_type == "stale_snapshot"


def test_tracks_versions_per_task_id() -> None:
    processor = ObservationProcessor()

    first_task = processor.push_task_snapshot(_snapshot(task_id="task-1", version=2))
    second_task = processor.push_task_snapshot(_snapshot(task_id="task-2", version=1))
    assert first_task.accepted is True
    assert second_task.accepted is True
