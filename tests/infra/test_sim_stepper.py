from __future__ import annotations

import importlib
import types

import pytest

from gazebo.sim_stepper import SimStepper


def test_sim_stepper_raises_import_error_when_gz_transport_unavailable(monkeypatch):
    def _always_fail(_name: str):
        raise ModuleNotFoundError("missing")

    monkeypatch.setattr(importlib, "import_module", _always_fail)
    with pytest.raises(ImportError):
        SimStepper("some_world")


def test_sim_stepper_imports_versioned_modules(monkeypatch):
    calls: list[str] = []

    class _FakeStats:
        class sim_time:
            sec = 0
            nsec = 0

    class _FakeNode:
        def subscribe(self, *_args):
            return None

        def request(self, *_args):
            return None

    def _fake_import(name: str):
        calls.append(name)
        if name == "gz.transport":
            raise ModuleNotFoundError("no plain module")
        if name == "gz.transport14":
            raise ModuleNotFoundError("no 14")
        if name == "gz.transport13":
            return types.SimpleNamespace(Node=_FakeNode)
        if name.endswith("world_control_pb2"):
            return types.SimpleNamespace(WorldControl=type("WorldControl", (), {}))
        if name.endswith("world_stats_pb2"):
            return types.SimpleNamespace(WorldStatistics=_FakeStats)
        raise ModuleNotFoundError(name)

    monkeypatch.setattr(importlib, "import_module", _fake_import)
    stepper = SimStepper("demo", physics_step_ms=1)
    assert stepper is not None
    assert "gz.transport13" in calls
