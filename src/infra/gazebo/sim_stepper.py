from __future__ import annotations

import importlib
import time
from typing import Any

_TRANSPORT_MODULES = (
    "gz.transport",
    "gz.transport14",
    "gz.transport13",
    "gz.transport12",
)
_WORLD_CONTROL_MODULES = (
    "gz.msgs.world_control_pb2",
    "gz.msgs14.world_control_pb2",
    "gz.msgs13.world_control_pb2",
    "gz.msgs12.world_control_pb2",
    "gz.msgs11.world_control_pb2",
    "gz.msgs10.world_control_pb2",
)
_WORLD_STATS_MODULES = (
    "gz.msgs.world_stats_pb2",
    "gz.msgs14.world_stats_pb2",
    "gz.msgs13.world_stats_pb2",
    "gz.msgs12.world_stats_pb2",
    "gz.msgs11.world_stats_pb2",
    "gz.msgs10.world_stats_pb2",
)


def _import_first(candidates: tuple[str, ...]) -> Any:
    last_error: Exception | None = None
    for module_name in candidates:
        try:
            return importlib.import_module(module_name)
        except Exception as exc:  # pragma: no cover
            last_error = exc
    raise ImportError(f"unable to import any of: {', '.join(candidates)}") from last_error


def _load_gz_bindings() -> tuple[Any, Any, Any]:
    transport_module = _import_first(_TRANSPORT_MODULES)
    world_control_module = _import_first(_WORLD_CONTROL_MODULES)
    world_stats_module = _import_first(_WORLD_STATS_MODULES)

    node_cls = getattr(transport_module, "Node", None)
    world_control_cls = getattr(world_control_module, "WorldControl", None)
    world_stats_cls = getattr(world_stats_module, "WorldStatistics", None)
    if node_cls is None or world_control_cls is None or world_stats_cls is None:
        raise ImportError("gz bindings are installed but required classes are missing")
    return node_cls, world_control_cls, world_stats_cls


class SimStepper:
    """Wrap gz-transport world control for explicit fixed-step simulation."""

    _POLL_INTERVAL_S = 0.001
    _STEP_TIMEOUT_S = 5.0

    def __init__(self, world_name: str, physics_step_ms: int = 1) -> None:
        if physics_step_ms <= 0:
            raise ValueError("physics_step_ms must be positive")
        try:
            node_cls, world_control_cls, world_stats_cls = _load_gz_bindings()
        except Exception as exc:
            raise ImportError("gz-transport Python bindings are not available.") from exc

        self._physics_step_ms = int(physics_step_ms)
        self._node = node_cls()
        self._world_control_cls = world_control_cls
        self._world_stats_cls = world_stats_cls
        self._control_topic = f"/world/{world_name}/control"
        self._stats_topic = f"/world/{world_name}/stats"
        self._latest_stats: Any = None

        self._node.subscribe(self._world_stats_cls, self._stats_topic, self._on_stats)

    def step(self, n_steps: int) -> None:
        if n_steps <= 0:
            raise ValueError("n_steps must be positive")

        before_us = self.sim_time_us()
        target_us = before_us + (n_steps * self._physics_step_ms * 1_000)

        msg = self._world_control_cls()
        msg.step = True
        msg.multi_step = int(n_steps)
        self._node.request(self._control_topic, msg)

        deadline = time.monotonic() + self._STEP_TIMEOUT_S
        while self.sim_time_us() < target_us:
            if time.monotonic() > deadline:
                break
            time.sleep(self._POLL_INTERVAL_S)

    def sim_time_us(self) -> int:
        stats = self._latest_stats
        if stats is None:
            return 0
        t = stats.sim_time
        return int(t.sec) * 1_000_000 + int(t.nsec) // 1_000

    def close(self) -> None:
        self._node = None
        self._latest_stats = None

    def _on_stats(self, msg: Any) -> None:
        self._latest_stats = msg
