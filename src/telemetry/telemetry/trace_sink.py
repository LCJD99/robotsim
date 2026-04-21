from __future__ import annotations

import json
from pathlib import Path
from collections.abc import Mapping

from telemetry.schema_contract import validate_record

KIND_TO_FILENAME = {
    "window_observation": "window_observation.jsonl",
    "plan": "plan.jsonl",
    "outcome": "outcome.jsonl",
    "task_events": "task_events.jsonl",
    "resource_samples": "resource_samples.jsonl",
}


class TraceSink:
    def __init__(self, root_dir: Path | str, experiment_id: str):
        self._base_dir = Path(root_dir) / experiment_id
        self._base_dir.mkdir(parents=True, exist_ok=True)

    def write(self, kind: str, record: Mapping[str, object]) -> None:
        validate_record(kind, record)
        path = self._base_dir / KIND_TO_FILENAME[kind]
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=True))
            handle.write("\n")
