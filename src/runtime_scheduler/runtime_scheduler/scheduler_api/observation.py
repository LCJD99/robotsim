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
