from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from time import strftime

from runtime_scheduler.scheduler_api.control import (
    CommandAcceptResult,
    CommandCoordinator,
    CommandPayload,
    validate_sync_command,
)
from runtime_scheduler.scheduler_api.fake_nodes import (
    build_demo_task_snapshot,
    build_fake_node_specs,
)
from runtime_scheduler.scheduler_api.merge_engine import merge_node_state


@dataclass(frozen=True, slots=True)
class MvpRunResult:
    experiment_id: str
    output_path: Path


def _ensure_experiment_id(experiment_id: str | None) -> str:
    if experiment_id:
        return experiment_id
    return strftime("%Y%m%d-%H%M%S-mvp")


def _to_command_result(
    command_type: str,
    target_id: str,
    command_id: str,
    accept: CommandAcceptResult,
    payload: CommandPayload,
) -> dict[str, object]:
    return {
        "command_type": command_type,
        "target_id": target_id,
        "command_id": command_id,
        "accepted": accept.accepted,
        "result_key": accept.result_key,
        "error_code": accept.error_code,
        "args": dict(payload.args),
    }


def run_mvp_once(output_root: Path | str = "traces", experiment_id: str | None = None) -> MvpRunResult:
    resolved_experiment_id = _ensure_experiment_id(experiment_id)
    output_dir = Path(output_root) / resolved_experiment_id
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "mvp_scheduler_result.json"

    snapshot = build_demo_task_snapshot()
    node_specs = build_fake_node_specs()
    coordinator = CommandCoordinator()

    effective_nodes: list[dict[str, object]] = []
    commands: list[dict[str, object]] = []
    for node_spec in node_specs:
        merged = merge_node_state(node_spec=node_spec, snapshots=(snapshot,))
        effective_nodes.append(
            {
                "node_id": node_spec.node_id,
                "activation": merged.activation.value,
                "priority": merged.priority.value,
                "core_always_on": node_spec.core_always_on,
            }
        )

        lifecycle_command = "start_node" if merged.activation.value == "required" else "stop_node"
        lifecycle_payload = CommandPayload(
            command_type=lifecycle_command,
            target_id=node_spec.node_id,
            args={"window_id": "window-1"},
        )
        lifecycle_command_id = f"cmd-{node_spec.node_id}-{lifecycle_command}"
        lifecycle_accept = coordinator.accept(command_id=lifecycle_command_id, payload=lifecycle_payload)
        commands.append(
            _to_command_result(
                command_type=lifecycle_command,
                target_id=node_spec.node_id,
                command_id=lifecycle_command_id,
                accept=lifecycle_accept,
                payload=lifecycle_payload,
            )
        )

        quota = (
            node_spec.cpu_quota.default_value
            if node_spec.cpu_quota.default_value is not None
            else node_spec.cpu_quota.min_value
        )
        validate_sync_command(node_spec=node_spec, field_name="cpu_quota", value=float(quota))
        quota_payload = CommandPayload(
            command_type="set_cpu_quota",
            target_id=node_spec.node_id,
            args={"value": float(quota)},
        )
        quota_command_id = f"cmd-{node_spec.node_id}-set-cpu"
        quota_accept = coordinator.accept(command_id=quota_command_id, payload=quota_payload)
        commands.append(
            _to_command_result(
                command_type="set_cpu_quota",
                target_id=node_spec.node_id,
                command_id=quota_command_id,
                accept=quota_accept,
                payload=quota_payload,
            )
        )

    probe_command_id = "cmd-probe-idempotency"
    coordinator.accept(
        command_id=probe_command_id,
        payload=CommandPayload(
            command_type="start_node",
            target_id="object_detector",
            args={"window_id": "window-1"},
        ),
    )
    conflict_result = coordinator.accept(
        command_id=probe_command_id,
        payload=CommandPayload(
            command_type="stop_node",
            target_id="object_detector",
            args={"window_id": "window-1"},
        ),
    )

    payload = {
        "experiment_id": resolved_experiment_id,
        "window_id": "window-1",
        "task_id": snapshot.task_id,
        "effective_nodes": effective_nodes,
        "commands": commands,
        "idempotency_probe": {
            "command_id": probe_command_id,
            "accepted": conflict_result.accepted,
            "error_code": conflict_result.error_code,
        },
    }
    output_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
    return MvpRunResult(experiment_id=resolved_experiment_id, output_path=output_path)
