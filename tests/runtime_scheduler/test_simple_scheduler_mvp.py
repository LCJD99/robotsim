from __future__ import annotations

import json

from runtime_scheduler.scheduler_api.simple_scheduler import run_mvp_once


def test_run_mvp_once_writes_result_json_to_traces(tmp_path) -> None:
    result = run_mvp_once(output_root=tmp_path, experiment_id="exp-mvp-1")

    assert result.experiment_id == "exp-mvp-1"
    assert result.output_path == tmp_path / "exp-mvp-1" / "mvp_scheduler_result.json"
    assert result.output_path.exists()

    payload = json.loads(result.output_path.read_text(encoding="utf-8"))
    assert payload["experiment_id"] == "exp-mvp-1"
    assert payload["window_id"] == "window-1"
    assert "effective_nodes" in payload
    assert "commands" in payload


def test_run_mvp_once_respects_core_node_and_reports_idempotency_conflict(tmp_path) -> None:
    result = run_mvp_once(output_root=tmp_path, experiment_id="exp-mvp-2")
    payload = json.loads(result.output_path.read_text(encoding="utf-8"))

    effective_nodes = {row["node_id"]: row for row in payload["effective_nodes"]}
    commands = payload["commands"]

    assert effective_nodes["controller_bridge"]["activation"] == "required"
    assert effective_nodes["object_detector"]["priority"] == "high"

    command_pairs = {(row["command_type"], row["target_id"]) for row in commands}
    assert ("start_node", "controller_bridge") in command_pairs
    assert ("start_node", "object_detector") in command_pairs
    assert ("stop_node", "camera_ingest") in command_pairs

    probe = payload["idempotency_probe"]
    assert probe["accepted"] is False
    assert probe["error_code"] == "CONFLICT"
