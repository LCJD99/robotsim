from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
from typing import Any

from runtime_scheduler.scheduler_api.errors import ApiError
from runtime_scheduler.scheduler_api.registry import NodeSpec


@dataclass(frozen=True)
class CommandPayload:
    command_type: str
    target_id: str
    args: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CommandAcceptResult:
    accepted: bool
    result_key: str | None = None
    error_code: str | None = None


class CommandCoordinator:
    def __init__(self) -> None:
        self._seen_payload_digest_by_command_id: dict[str, str] = {}
        self._result_key_by_command_id: dict[str, str] = {}

    @staticmethod
    def _digest(payload: CommandPayload) -> str:
        canonical_payload = {
            "command_type": payload.command_type,
            "target_id": payload.target_id,
            "args": payload.args,
        }
        encoded = json.dumps(canonical_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def accept(self, command_id: str, payload: CommandPayload) -> CommandAcceptResult:
        digest = self._digest(payload)
        existing_digest = self._seen_payload_digest_by_command_id.get(command_id)
        if existing_digest is None:
            self._seen_payload_digest_by_command_id[command_id] = digest
            self._result_key_by_command_id[command_id] = digest
            return CommandAcceptResult(accepted=True, result_key=digest)
        if existing_digest != digest:
            return CommandAcceptResult(accepted=False, error_code="CONFLICT")
        return CommandAcceptResult(accepted=True, result_key=self._result_key_by_command_id[command_id])


def validate_sync_command(node_spec: NodeSpec, field_name: str, value: float) -> None:
    if field_name == "cpu_quota":
        bounds = node_spec.cpu_quota
    elif field_name == "max_concurrency":
        bounds = node_spec.max_concurrency
    else:
        return

    if not bounds.contains(value):
        raise ApiError(
            code="INVALID_ARG",
            message=f"{field_name} is out of bounds",
            details={
                "reason": "bound_violation",
                "field": field_name,
                "min": bounds.min_value,
                "max": bounds.max_value,
                "value": value,
            },
        )
