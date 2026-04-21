# Step-Locked Simulation Loop & Real Resource Sampling — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the wall-clock scheduler loop with a Gazebo step-locked loop driven by gz-transport `WorldControl`, and replace the all-zero resource sampler with a real cgroup/nvidia-smi/procfs sampler.

**Architecture:** `SteppedExperimentLoop` owns the `Observation → Plan → Outcome → SimStep` cadence. `SimStepper` encapsulates gz-transport and raises `ImportError` when unavailable. `RealResourceSampler` reads system interfaces with per-source silent fallback. `main()` tries `run_stepped_experiment()` first and falls back to the existing `run_experiment()` on `ImportError`.

**Tech Stack:** Python ≥ 3.10, `gz-transport` Python bindings (`gz.transport`, `gz.msgs`), `subprocess` (nvidia-smi), `pytest`, `pathlib`, `dataclasses`.

**Spec:** `docs/superpowers/specs/2026-04-22-stepped-loop-real-sampler-design.md`

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `src/infra/gazebo/__init__.py` | Create | Package marker |
| `src/infra/gazebo/sim_stepper.py` | Create | gz-transport WorldControl wrapper |
| `src/telemetry/telemetry/real_resource_sampler.py` | Create | cgroup / nvidia-smi / procfs sampler |
| `src/runtime_scheduler/runtime_scheduler/stepped_loop.py` | Create | Step-locked experiment loop |
| `src/runtime_scheduler/runtime_scheduler/config.py` | Modify | Add `SimConfig` dataclass + `sim` field to `Config` |
| `src/runtime_scheduler/runtime_scheduler/main.py` | Modify | Add `run_stepped_experiment()` + update `main()` |
| `experiment_configs/v1_dynamic_dense.yaml` | Modify | Add `sim:` block |
| `src/sim_bringup/launch/sim_stack.launch.py` | Modify | Remove `-r` flag from `gz_args` |
| `tests/infra/__init__.py` | Create | Package marker for test discovery |
| `tests/infra/test_sim_stepper.py` | Create | `ImportError` behaviour without gz-transport |
| `tests/telemetry/test_real_resource_sampler.py` | Create | Unit tests with mock cgroup files + mock subprocess |
| `tests/runtime_scheduler/test_stepped_loop.py` | Create | Unit tests with mock stepper and sampler |
| `tests/integration/test_sim_stack_config_contract.py` | Modify | Assert `sim` block and new YAML keys |

---

## Task 1: Add `SimConfig` to `config.py` and `v1_dynamic_dense.yaml`

**Files:**
- Modify: `src/runtime_scheduler/runtime_scheduler/config.py`
- Modify: `experiment_configs/v1_dynamic_dense.yaml`
- Test: `tests/runtime_scheduler/test_config.py`

- [ ] **Step 1: Write the failing tests**

Add these two test functions to `tests/runtime_scheduler/test_config.py`:

```python
def test_load_config_reads_sim_fields():
    cfg = load_config(BASELINE_CONFIG)
    assert cfg.sim.world_name == "dynamic_obstacle_dense"
    assert cfg.sim.physics_step_ms == 1


def test_load_config_sim_defaults_when_key_absent(tmp_path):
    # FULL_CONFIG_TEXT has no sim: block — sim defaults must apply
    path = tmp_path / "no_sim.yaml"
    path.write_text(FULL_CONFIG_TEXT + "\n")
    cfg = load_config(path)
    assert cfg.sim.world_name == "dynamic_obstacle_dense"
    assert cfg.sim.physics_step_ms == 1
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /home/dawnat9/code-workspace/ai4heuristic/robotsim
python3 -m pytest tests/runtime_scheduler/test_config.py::test_load_config_reads_sim_fields tests/runtime_scheduler/test_config.py::test_load_config_sim_defaults_when_key_absent -v
```

Expected: `FAILED` — `Config` has no `sim` attribute.

- [ ] **Step 3: Add `SimConfig` to `config.py`**

Add the new dataclass after `TraceConfig` and update `Config` and `load_config()`:

```python
# After TraceConfig definition, before Config:

@dataclass(frozen=True, slots=True)
class SimConfig:
    world_name: str = "dynamic_obstacle_dense"
    physics_step_ms: int = 1
```

Update `Config` to include the new field (add after `trace: TraceConfig`):

```python
@dataclass(frozen=True, slots=True)
class Config:
    experiment: ExperimentConfig
    scenario: ScenarioConfig
    scheduler: SchedulerConfig
    trigger: TriggerConfig
    agent: AgentConfig
    agent_workload: AgentWorkloadConfig
    vee: VeeConfig
    trace: TraceConfig
    sim: SimConfig = SimConfig()
```

Update `load_config()` — add after the `trace = _require_mapping(...)` line:

```python
    sim_raw = raw.get("sim", {})
    if not isinstance(sim_raw, Mapping):
        raise ValueError("expected mapping at sim")
```

Update the `return Config(...)` call — add `sim=` as the last keyword argument:

```python
        sim=SimConfig(
            world_name=str(sim_raw.get("world_name", "dynamic_obstacle_dense")),
            physics_step_ms=int(sim_raw.get("physics_step_ms", 1)),
        ),
```

- [ ] **Step 4: Add `sim:` block to `v1_dynamic_dense.yaml`**

Append at the end of `experiment_configs/v1_dynamic_dense.yaml`:

```yaml

sim:
  world_name: dynamic_obstacle_dense
  physics_step_ms: 1          # Gazebo default physics rate (1 kHz)
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
python3 -m pytest tests/runtime_scheduler/test_config.py -v
```

Expected: all tests `PASSED`.

- [ ] **Step 6: Run full suite to confirm no regressions**

```bash
python3 -m pytest -q
```

Expected: all existing tests pass.

- [ ] **Step 7: Commit**

```bash
git add src/runtime_scheduler/runtime_scheduler/config.py experiment_configs/v1_dynamic_dense.yaml tests/runtime_scheduler/test_config.py
git commit -m "feat: add SimConfig dataclass and sim block to config and yaml"
```

---

## Task 2: Update integration contract test for `sim:` block

**Files:**
- Modify: `tests/integration/test_sim_stack_config_contract.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/integration/test_sim_stack_config_contract.py`:

```python
import yaml
from pathlib import Path


def test_yaml_contains_sim_block():
    raw = yaml.safe_load(Path("experiment_configs/v1_dynamic_dense.yaml").read_text())
    assert "sim" in raw, "expected top-level 'sim' key in v1_dynamic_dense.yaml"


def test_sim_world_name_is_nonempty_string():
    raw = yaml.safe_load(Path("experiment_configs/v1_dynamic_dense.yaml").read_text())
    world_name = raw["sim"]["world_name"]
    assert isinstance(world_name, str) and world_name.strip(), \
        "sim.world_name must be a non-empty string"


def test_sim_physics_step_ms_is_positive_int():
    raw = yaml.safe_load(Path("experiment_configs/v1_dynamic_dense.yaml").read_text())
    step_ms = raw["sim"]["physics_step_ms"]
    assert isinstance(step_ms, int) and step_ms > 0, \
        "sim.physics_step_ms must be a positive integer"
```

- [ ] **Step 2: Run tests to verify they pass immediately** (YAML was already updated in Task 1)

```bash
python3 -m pytest tests/integration/test_sim_stack_config_contract.py -v
```

Expected: all tests `PASSED`.

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_sim_stack_config_contract.py
git commit -m "test: extend sim_stack config contract to assert sim block"
```

---

## Task 3: Create `SimStepper`

**Files:**
- Create: `src/infra/gazebo/__init__.py`
- Create: `src/infra/gazebo/sim_stepper.py`
- Create: `tests/infra/__init__.py`
- Create: `tests/infra/test_sim_stepper.py`

`pyproject.toml` already contains `"src/infra"` in `pythonpath`, so `from gazebo.sim_stepper import SimStepper` resolves correctly.

- [ ] **Step 1: Write the failing test**

Create `tests/infra/__init__.py` (empty):

```python
```

Create `tests/infra/test_sim_stepper.py`:

```python
from __future__ import annotations

import sys
import pytest


def test_sim_stepper_raises_import_error_when_gz_transport_unavailable(monkeypatch):
    # Block gz.transport and gz.msgs from being importable.
    monkeypatch.setitem(sys.modules, "gz", None)
    monkeypatch.setitem(sys.modules, "gz.transport", None)
    monkeypatch.setitem(sys.modules, "gz.msgs", None)
    monkeypatch.setitem(sys.modules, "gz.msgs.world_control_pb2", None)

    # Force re-import of sim_stepper with the patched modules.
    monkeypatch.delitem(sys.modules, "gazebo.sim_stepper", raising=False)

    with pytest.raises(ImportError):
        from gazebo.sim_stepper import SimStepper  # noqa: F401
        SimStepper("some_world")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python3 -m pytest tests/infra/test_sim_stepper.py -v
```

Expected: `FAILED` — `gazebo.sim_stepper` does not exist yet.

- [ ] **Step 3: Create `src/infra/gazebo/__init__.py`**

```python
```

- [ ] **Step 4: Create `src/infra/gazebo/sim_stepper.py`**

```python
from __future__ import annotations

import time

try:
    import gz.transport  # type: ignore[import]
    from gz.msgs.world_control_pb2 import WorldControl  # type: ignore[import]
    from gz.msgs.world_stats_pb2 import WorldStatistics  # type: ignore[import]
    _GZ_AVAILABLE = True
except Exception as exc:
    _GZ_AVAILABLE = False
    _GZ_IMPORT_ERROR = exc


class SimStepper:
    """Wraps gz-transport WorldControl to step a paused Gazebo simulation.

    Raises ImportError if gz-transport Python bindings are not available.
    """

    _POLL_INTERVAL_S: float = 0.001   # 1 ms poll interval when waiting for step

    def __init__(self, world_name: str, physics_step_ms: int = 1) -> None:
        if not _GZ_AVAILABLE:
            raise ImportError(
                "gz-transport Python bindings are not available. "
                "Install gz-transport or run without --stepped mode."
            ) from _GZ_IMPORT_ERROR

        self._world_name = world_name
        self._physics_step_ms = physics_step_ms
        self._node = gz.transport.Node()

        self._control_topic = f"/world/{world_name}/control"
        self._stats_topic = f"/world/{world_name}/stats"

        # Latest stats message, updated by subscription callback.
        self._latest_stats: WorldStatistics | None = None

        self._node.subscribe(
            WorldStatistics,
            self._stats_topic,
            self._on_stats,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def step(self, n_steps: int) -> None:
        """Advance the simulation by *n_steps* physics steps and block until done."""
        before_us = self.sim_time_us()
        expected_advance_us = n_steps * self._physics_step_ms * 1_000

        msg = WorldControl()
        msg.step = True
        msg.multi_step = n_steps
        self._node.request(self._control_topic, msg)

        deadline = time.monotonic() + 5.0  # 5 s safety timeout
        while True:
            current_us = self.sim_time_us()
            if current_us >= before_us + expected_advance_us:
                break
            if time.monotonic() > deadline:
                break
            time.sleep(self._POLL_INTERVAL_S)

    def sim_time_us(self) -> int:
        """Return the current simulation time in microseconds."""
        stats = self._latest_stats
        if stats is None:
            return 0
        t = stats.sim_time
        return t.sec * 1_000_000 + t.nsec // 1_000

    def close(self) -> None:
        """Release gz-transport resources."""
        # gz.transport.Node does not require explicit teardown, but we
        # unset references so the GC can reclaim the subscription.
        self._node = None  # type: ignore[assignment]
        self._latest_stats = None

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _on_stats(self, msg: WorldStatistics) -> None:
        self._latest_stats = msg
```

- [ ] **Step 5: Run test to verify it passes**

```bash
python3 -m pytest tests/infra/test_sim_stepper.py -v
```

Expected: `PASSED`.

- [ ] **Step 6: Run full suite**

```bash
python3 -m pytest -q
```

Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
git add src/infra/gazebo/__init__.py src/infra/gazebo/sim_stepper.py tests/infra/__init__.py tests/infra/test_sim_stepper.py
git commit -m "feat: add SimStepper with gz-transport WorldControl and ImportError fallback"
```

---

## Task 4: Create `RealResourceSampler`

**Files:**
- Create: `src/telemetry/telemetry/real_resource_sampler.py`
- Create: `tests/telemetry/test_real_resource_sampler.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/telemetry/test_real_resource_sampler.py`:

```python
from __future__ import annotations

import subprocess
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from telemetry.real_resource_sampler import RealResourceSampler


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_cgroup_files(root: Path, cpu_usage_usec: int, mem_current: int, mem_max: int) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "cpu.stat").write_text(f"usage_usec {cpu_usage_usec}\n")
    (root / "memory.current").write_text(f"{mem_current}\n")
    (root / "memory.max").write_text(f"{mem_max}\n")


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

def test_sample_returns_required_schema_keys(tmp_path):
    _write_cgroup_files(tmp_path, 0, 0, 1)
    s = RealResourceSampler(cgroup_root=str(tmp_path), sample_interval_ms=50)
    result = s.sample()
    assert set(result) >= {
        "schema_version", "cpu", "memory", "gpu", "network", "scope"
    }
    assert result["schema_version"] == "v1"
    assert result["scope"] == "system"


# ---------------------------------------------------------------------------
# CPU delta sampling
# ---------------------------------------------------------------------------

def test_cpu_utilization_computed_from_delta(tmp_path):
    _write_cgroup_files(tmp_path, 0, 0, 1)
    s = RealResourceSampler(cgroup_root=str(tmp_path), sample_interval_ms=50)
    s.sample()  # baseline read

    # Advance usage by 25_000 µs over a 50 ms interval → 50 % utilisation
    _write_cgroup_files(tmp_path, 25_000, 0, 1)
    with patch("time.monotonic", side_effect=[0.0, 0.05]):
        result = s.sample()

    cpu = result["cpu"]["utilization_total"]
    assert 0.0 <= cpu <= 1.0


# ---------------------------------------------------------------------------
# Memory
# ---------------------------------------------------------------------------

def test_memory_reads_current_and_max(tmp_path):
    _write_cgroup_files(tmp_path, 0, 4_000_000, 8_000_000)
    s = RealResourceSampler(cgroup_root=str(tmp_path), sample_interval_ms=50)
    result = s.sample()
    assert result["memory"]["used_bytes"] == 4_000_000
    assert result["memory"]["available_bytes"] == 4_000_000  # max - current


# ---------------------------------------------------------------------------
# GPU via nvidia-smi mock
# ---------------------------------------------------------------------------

def test_gpu_parsed_from_nvidia_smi(tmp_path):
    _write_cgroup_files(tmp_path, 0, 0, 1)
    s = RealResourceSampler(cgroup_root=str(tmp_path), sample_interval_ms=50)

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "42, 1024\n"

    with patch("subprocess.run", return_value=mock_result):
        result = s.sample()

    assert result["gpu"]["utilization"] == pytest.approx(0.42)
    assert result["gpu"]["memory_used_bytes"] == 1024 * 1024 * 1024


# ---------------------------------------------------------------------------
# Fallback when cgroup path absent
# ---------------------------------------------------------------------------

def test_all_metrics_fallback_to_zero_when_cgroup_absent(tmp_path):
    missing = tmp_path / "nonexistent"
    s = RealResourceSampler(cgroup_root=str(missing), sample_interval_ms=50)

    with patch("subprocess.run", side_effect=FileNotFoundError):
        result = s.sample()

    assert result["cpu"]["utilization_total"] == 0.0
    assert result["memory"]["used_bytes"] == 0
    assert result["gpu"]["utilization"] == 0.0
    assert result["network"]["tx_rate_bps"] == 0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/telemetry/test_real_resource_sampler.py -v
```

Expected: `FAILED` — module does not exist yet.

- [ ] **Step 3: Create `src/telemetry/telemetry/real_resource_sampler.py`**

```python
from __future__ import annotations

import subprocess
import time
from pathlib import Path


class RealResourceSampler:
    """Reads real resource metrics from cgroup, nvidia-smi, and procfs.

    Each source falls back silently to zero if the path or binary is unavailable,
    so the sampler works on development machines without cgroup or GPU.
    """

    def __init__(
        self,
        cgroup_root: str = "/sys/fs/cgroup/vee",
        sample_interval_ms: int = 50,
    ) -> None:
        self._cgroup = Path(cgroup_root)
        self._sample_interval_ms = sample_interval_ms

        # State for delta calculations.
        self._prev_cpu_usage_usec: int = 0
        self._prev_cpu_wall_s: float = time.monotonic()
        self._prev_net_tx_bytes: int = 0
        self._prev_net_rx_bytes: int = 0
        self._prev_net_wall_s: float = time.monotonic()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def sample(self) -> dict[str, object]:
        return {
            "schema_version": "v1",
            "scope": "system",
            "cpu": {"utilization_total": self._cpu_utilization()},
            "memory": self._memory(),
            "gpu": self._gpu(),
            "network": self._network(),
        }

    # ------------------------------------------------------------------
    # CPU
    # ------------------------------------------------------------------

    def _cpu_utilization(self) -> float:
        stat_path = self._cgroup / "cpu.stat"
        try:
            usage_usec = self._read_cpu_stat_usage(stat_path)
        except Exception:
            return 0.0

        now = time.monotonic()
        delta_usec = usage_usec - self._prev_cpu_usage_usec
        delta_wall_s = now - self._prev_cpu_wall_s

        self._prev_cpu_usage_usec = usage_usec
        self._prev_cpu_wall_s = now

        if delta_wall_s <= 0:
            return 0.0
        return min(delta_usec / (delta_wall_s * 1_000_000), 1.0)

    @staticmethod
    def _read_cpu_stat_usage(path: Path) -> int:
        for line in path.read_text().splitlines():
            if line.startswith("usage_usec"):
                return int(line.split()[1])
        raise ValueError(f"usage_usec not found in {path}")

    # ------------------------------------------------------------------
    # Memory
    # ------------------------------------------------------------------

    def _memory(self) -> dict[str, int]:
        try:
            used = int((self._cgroup / "memory.current").read_text().strip())
            max_bytes_raw = (self._cgroup / "memory.max").read_text().strip()
            max_bytes = int(max_bytes_raw) if max_bytes_raw != "max" else 0
            available = max(max_bytes - used, 0) if max_bytes > 0 else 0
            return {"used_bytes": used, "available_bytes": available}
        except Exception:
            return {"used_bytes": 0, "available_bytes": 0}

    # ------------------------------------------------------------------
    # GPU
    # ------------------------------------------------------------------

    def _gpu(self) -> dict[str, object]:
        try:
            result = subprocess.run(
                [
                    "nvidia-smi",
                    "--query-gpu=utilization.gpu,memory.used",
                    "--format=csv,noheader,nounits",
                ],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if result.returncode != 0:
                return {"utilization": 0.0, "memory_used_bytes": 0}
            parts = result.stdout.strip().split(",")
            util_pct = float(parts[0].strip())
            mem_mib = float(parts[1].strip())
            return {
                "utilization": round(util_pct / 100.0, 4),
                "memory_used_bytes": int(mem_mib * 1024 * 1024),
            }
        except Exception:
            return {"utilization": 0.0, "memory_used_bytes": 0}

    # ------------------------------------------------------------------
    # Network
    # ------------------------------------------------------------------

    def _network(self) -> dict[str, int]:
        try:
            tx, rx = self._read_net_bytes()
        except Exception:
            return {"tx_rate_bps": 0, "rx_rate_bps": 0}

        now = time.monotonic()
        delta_s = now - self._prev_net_wall_s
        delta_tx = tx - self._prev_net_tx_bytes
        delta_rx = rx - self._prev_net_rx_bytes

        self._prev_net_tx_bytes = tx
        self._prev_net_rx_bytes = rx
        self._prev_net_wall_s = now

        if delta_s <= 0:
            return {"tx_rate_bps": 0, "rx_rate_bps": 0}
        return {
            "tx_rate_bps": int(delta_tx * 8 / delta_s),
            "rx_rate_bps": int(delta_rx * 8 / delta_s),
        }

    @staticmethod
    def _read_net_bytes() -> tuple[int, int]:
        total_tx = 0
        total_rx = 0
        lines = Path("/proc/net/dev").read_text().splitlines()
        for line in lines[2:]:  # skip two header lines
            parts = line.split()
            if len(parts) < 10:
                continue
            iface = parts[0].rstrip(":")
            if iface == "lo":
                continue
            total_rx += int(parts[1])
            total_tx += int(parts[9])
        return total_tx, total_rx
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python3 -m pytest tests/telemetry/test_real_resource_sampler.py -v
```

Expected: all tests `PASSED`.

- [ ] **Step 5: Run full suite**

```bash
python3 -m pytest -q
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/telemetry/telemetry/real_resource_sampler.py tests/telemetry/test_real_resource_sampler.py
git commit -m "feat: add RealResourceSampler with cgroup/nvidia-smi/procfs and zero fallback"
```

---

## Task 5: Create `SteppedExperimentLoop`

**Files:**
- Create: `src/runtime_scheduler/runtime_scheduler/stepped_loop.py`
- Create: `tests/runtime_scheduler/test_stepped_loop.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/runtime_scheduler/test_stepped_loop.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pytest

from runtime_scheduler.config import (
    AgentConfig,
    AgentWorkloadConfig,
    Config,
    ExperimentConfig,
    LocalToolArrivalConfig,
    ScenarioConfig,
    SchedulerConfig,
    SimConfig,
    TraceConfig,
    TriggerConfig,
    VeeConfig,
    VeeCpuConfig,
    VeeGpuConfig,
    VeeMemoryConfig,
)
from runtime_scheduler.stepped_loop import SteppedExperimentLoop
from runtime_scheduler.workload_generator import PoissonLocalToolGenerator
from telemetry.trace_sink import TraceSink


# ---------------------------------------------------------------------------
# Minimal config for tests — 3 windows of 50 ms = 150 ms total sim time
# ---------------------------------------------------------------------------

def _make_config(duration_sec: int = 1) -> Config:
    return Config(
        experiment=ExperimentConfig(duration_sec=duration_sec, id_format="%Y%m%d-%H%M%S"),
        scenario=ScenarioConfig(type="dynamic_obstacle_dense"),
        scheduler=SchedulerConfig(impl="critical_first_fifo", window_ms=50),
        trigger=TriggerConfig(impl="hybrid", cooldown_windows=10),
        agent=AgentConfig(enabled_task_types=("LOCAL_TOOL",)),
        agent_workload=AgentWorkloadConfig(
            generator="poisson",
            seed=0,
            local_tool=LocalToolArrivalConfig(lambda_per_sec=0.0, max_arrivals_per_window=0),
        ),
        vee=VeeConfig(
            profile="test",
            cpu=VeeCpuConfig(cpuset="0", quota="100000 1000000"),
            memory=VeeMemoryConfig(high="1G", max="2G"),
            gpu=VeeGpuConfig(provider="none"),
        ),
        trace=TraceConfig(root_dir=Path("traces")),
        sim=SimConfig(world_name="test_world", physics_step_ms=1),
    )


# ---------------------------------------------------------------------------
# Mock stepper: sim_time_us() advances by window_ms * 1000 on each call
# ---------------------------------------------------------------------------

class MockStepper:
    def __init__(self, window_ms: int) -> None:
        self._step_us = window_ms * 1_000
        self._current_us = 0
        self.step_calls: int = 0

    def sim_time_us(self) -> int:
        return self._current_us

    def step(self, n_steps: int) -> None:
        self._current_us += self._step_us
        self.step_calls += 1

    def close(self) -> None:
        pass


# ---------------------------------------------------------------------------
# Mock sampler: returns a fixed zero resource dict
# ---------------------------------------------------------------------------

def _zero_sample() -> dict:
    return {
        "schema_version": "v1",
        "scope": "system",
        "cpu": {"utilization_total": 0.0},
        "memory": {"used_bytes": 0, "available_bytes": 0},
        "gpu": {"utilization": 0.0, "memory_used_bytes": 0},
        "network": {"tx_rate_bps": 0, "rx_rate_bps": 0},
    }


class MockSampler:
    def sample(self) -> dict:
        return _zero_sample()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_loop_exits_after_correct_number_of_windows(tmp_path):
    config = _make_config(duration_sec=1)  # 1 s / 50 ms = 20 windows
    stepper = MockStepper(window_ms=50)
    sampler = MockSampler()
    sink = TraceSink(root_dir=tmp_path, experiment_id="test-exp-1")
    generator = PoissonLocalToolGenerator(
        lambda_per_sec=0.0, window_ms=50, seed=0, max_arrivals_per_window=0
    )

    loop = SteppedExperimentLoop(
        stepper=stepper,
        sampler=sampler,
        generator=generator,
        sink=sink,
        config=config,
        experiment_id="test-exp-1",
    )
    loop.run()

    assert stepper.step_calls == 20


def test_loop_writes_one_resource_sample_per_window(tmp_path):
    config = _make_config(duration_sec=1)
    stepper = MockStepper(window_ms=50)
    sampler = MockSampler()
    sink = TraceSink(root_dir=tmp_path, experiment_id="test-exp-2")
    generator = PoissonLocalToolGenerator(
        lambda_per_sec=0.0, window_ms=50, seed=0, max_arrivals_per_window=0
    )

    loop = SteppedExperimentLoop(
        stepper=stepper,
        sampler=sampler,
        generator=generator,
        sink=sink,
        config=config,
        experiment_id="test-exp-2",
    )
    loop.run()

    resource_file = tmp_path / "test-exp-2" / "resource_samples.jsonl"
    assert resource_file.exists()
    lines = [l for l in resource_file.read_text().splitlines() if l.strip()]
    assert len(lines) == 20


def test_loop_writes_one_plan_per_window(tmp_path):
    config = _make_config(duration_sec=1)
    stepper = MockStepper(window_ms=50)
    sampler = MockSampler()
    sink = TraceSink(root_dir=tmp_path, experiment_id="test-exp-3")
    generator = PoissonLocalToolGenerator(
        lambda_per_sec=0.0, window_ms=50, seed=0, max_arrivals_per_window=0
    )

    loop = SteppedExperimentLoop(
        stepper=stepper,
        sampler=sampler,
        generator=generator,
        sink=sink,
        config=config,
        experiment_id="test-exp-3",
    )
    loop.run()

    plan_file = tmp_path / "test-exp-3" / "plan.jsonl"
    assert plan_file.exists()
    lines = [l for l in plan_file.read_text().splitlines() if l.strip()]
    assert len(lines) == 20
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/runtime_scheduler/test_stepped_loop.py -v
```

Expected: `FAILED` — `stepped_loop` module does not exist yet.

- [ ] **Step 3: Create `src/runtime_scheduler/runtime_scheduler/stepped_loop.py`**

```python
from __future__ import annotations

from runtime_scheduler.config import Config
from runtime_scheduler.runtime_loop import run_single_window
from runtime_scheduler.workload_generator import PoissonLocalToolGenerator
from telemetry.trace_sink import TraceSink


def _build_task_event(experiment_id: str, arrival: dict) -> dict:
    return {
        "schema_version": "v1",
        "experiment_id": experiment_id,
        "event_id": f"evt-{arrival['task_id']}",
        "event_type": "TASK_ARRIVAL",
        "timestamp_us": arrival["timestamp_us"],
        "window_id": arrival["window_id"],
        "task_id": arrival["task_id"],
        "request_id": arrival["request_id"],
        "task_type": "LOCAL_TOOL",
        "source": "generator",
        "arrival_source": arrival["arrival_source"],
        "generator_seed": arrival["generator_seed"],
        "lambda_per_sec": arrival["lambda_per_sec"],
    }


class SteppedExperimentLoop:
    """Drives the Observation → Plan → Outcome → SimStep cadence.

    Each iteration corresponds to one scheduler window (default 50 ms of sim time).
    The loop exits automatically when sim_time reaches the configured duration.
    """

    def __init__(
        self,
        stepper: object,
        sampler: object,
        generator: PoissonLocalToolGenerator,
        sink: TraceSink,
        config: Config,
        experiment_id: str,
    ) -> None:
        self._stepper = stepper
        self._sampler = sampler
        self._generator = generator
        self._sink = sink
        self._config = config
        self._experiment_id = experiment_id

    def run(self) -> None:
        cfg = self._config
        n_steps = cfg.scheduler.window_ms // cfg.sim.physics_step_ms
        duration_us = int(cfg.experiment.duration_sec * 1_000_000)

        window_idx = 0
        while self._stepper.sim_time_us() < duration_us:
            timestamp_us = self._stepper.sim_time_us()
            window_id = f"window-{window_idx + 1}"

            # ① Observe
            raw = self._sampler.sample()
            resource_record: dict = {
                **raw,
                "experiment_id": self._experiment_id,
                "sample_id": f"sample-{window_idx + 1}",
                "timestamp_us": timestamp_us,
                "window_id": window_id,
            }

            # ② Task arrivals
            arrivals = self._generator.next_arrivals(window_id, timestamp_us)
            tasks = [
                {"task_id": a["task_id"], "priority_class": "ELASTIC"} for a in arrivals
            ]
            for arrival in arrivals:
                self._sink.write(
                    "task_events", _build_task_event(self._experiment_id, arrival)
                )

            # ③ Schedule
            observation, plan, outcome = run_single_window(window_id, timestamp_us, tasks)

            # ④ Trace
            self._sink.write("window_observation", observation)
            self._sink.write("plan", plan)
            self._sink.write("outcome", outcome)
            self._sink.write("resource_samples", resource_record)

            # ⑤ Advance sim
            self._stepper.step(n_steps)
            window_idx += 1
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python3 -m pytest tests/runtime_scheduler/test_stepped_loop.py -v
```

Expected: all three tests `PASSED`.

- [ ] **Step 5: Run full suite**

```bash
python3 -m pytest -q
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/runtime_scheduler/runtime_scheduler/stepped_loop.py tests/runtime_scheduler/test_stepped_loop.py
git commit -m "feat: add SteppedExperimentLoop with Observation→Plan→Step cadence"
```

---

## Task 6: Wire `run_stepped_experiment()` into `main.py`

**Files:**
- Modify: `src/runtime_scheduler/runtime_scheduler/main.py`

No new test file needed — the existing `test_stepped_loop.py` exercises `SteppedExperimentLoop` directly. We verify `main()` behaviour with a smoke-run using the existing fallback path.

- [ ] **Step 1: Add imports and `run_stepped_experiment()` to `main.py`**

Add these imports near the top of `main.py`, after the existing imports:

```python
from runtime_scheduler.stepped_loop import SteppedExperimentLoop
from telemetry.real_resource_sampler import RealResourceSampler
```

Add the new function before `main()`:

```python
def run_stepped_experiment(output_root: Path, config: Config) -> None:
    """Run the step-locked experiment loop using gz-transport SimStepper.

    Raises ImportError if gz-transport Python bindings are not available.
    """
    from gazebo.sim_stepper import SimStepper  # deferred import — raises ImportError if absent

    experiment_id = make_experiment_id()
    stepper = SimStepper(config.sim.world_name, config.sim.physics_step_ms)
    sampler = RealResourceSampler(sample_interval_ms=config.scheduler.window_ms)
    sink = TraceSink(root_dir=output_root, experiment_id=experiment_id)
    generator = PoissonLocalToolGenerator(
        lambda_per_sec=config.agent_workload.local_tool.lambda_per_sec,
        window_ms=config.scheduler.window_ms,
        seed=config.agent_workload.seed,
        max_arrivals_per_window=config.agent_workload.local_tool.max_arrivals_per_window,
    )
    loop = SteppedExperimentLoop(
        stepper=stepper,
        sampler=sampler,
        generator=generator,
        sink=sink,
        config=config,
        experiment_id=experiment_id,
    )
    try:
        loop.run()
    finally:
        stepper.close()
```

- [ ] **Step 2: Update `main()` to try stepped first, fallback to wall-clock**

Replace the existing `main()` function:

```python
def main() -> None:
    config = load_config(CONFIG_PATH)
    try:
        run_stepped_experiment(output_root=config.trace.root_dir, config=config)
    except ImportError:
        import warnings
        warnings.warn(
            "gz-transport Python bindings not found; "
            "falling back to wall-clock run_experiment(). "
            "Install gz-transport to enable step-locked simulation.",
            stacklevel=1,
        )
        run_experiment(output_root=config.trace.root_dir, config=config)
```

- [ ] **Step 3: Run full suite to confirm nothing is broken**

```bash
python3 -m pytest -q
```

Expected: all tests pass.

- [ ] **Step 4: Smoke-run `main()` on the development machine (gz-transport absent → fallback)**

```bash
cd /home/dawnat9/code-workspace/ai4heuristic/robotsim
python3 -m runtime_scheduler.main
```

Expected: a warning about gz-transport, then traces written to `traces/` directory. Verify:

```bash
ls traces/
```

Expected: a timestamped experiment directory containing `plan.jsonl`, `outcome.jsonl`, `resource_samples.jsonl`, etc.

- [ ] **Step 5: Commit**

```bash
git add src/runtime_scheduler/runtime_scheduler/main.py
git commit -m "feat: wire run_stepped_experiment into main with ImportError fallback"
```

---

## Task 7: Update launch file — start Gazebo paused

**Files:**
- Modify: `src/sim_bringup/launch/sim_stack.launch.py`
- Test: `tests/integration/test_sim_stack_config_contract.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/integration/test_sim_stack_config_contract.py`:

```python
def test_sim_stack_launch_starts_gazebo_paused():
    launch_text = Path("src/sim_bringup/launch/sim_stack.launch.py").read_text(encoding="utf-8")
    assert "-r" not in launch_text.replace("# -r", ""), \
        "Gazebo must not start with -r (auto-run); simulation is driven by SteppedExperimentLoop"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python3 -m pytest tests/integration/test_sim_stack_config_contract.py::test_sim_stack_launch_starts_gazebo_paused -v
```

Expected: `FAILED` — `-r` is still present in the launch file.

- [ ] **Step 3: Remove `-r` from `sim_stack.launch.py`**

In `src/sim_bringup/launch/sim_stack.launch.py`, change:

```python
        launch_arguments={"gz_args": ["-r -s ", world]}.items(),
```

to:

```python
        launch_arguments={"gz_args": ["-s ", world]}.items(),
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python3 -m pytest tests/integration/test_sim_stack_config_contract.py -v
```

Expected: all tests `PASSED`.

- [ ] **Step 5: Run full suite**

```bash
python3 -m pytest -q
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/sim_bringup/launch/sim_stack.launch.py tests/integration/test_sim_stack_config_contract.py
git commit -m "feat: start Gazebo paused; simulation stepped by SteppedExperimentLoop"
```

---

## Final Verification

- [ ] **Run complete test suite one last time**

```bash
cd /home/dawnat9/code-workspace/ai4heuristic/robotsim
python3 -m pytest -q
```

Expected output: all tests pass, zero failures, zero errors.

- [ ] **Confirm all planned files exist**

```bash
ls src/infra/gazebo/sim_stepper.py \
   src/telemetry/telemetry/real_resource_sampler.py \
   src/runtime_scheduler/runtime_scheduler/stepped_loop.py \
   tests/infra/test_sim_stepper.py \
   tests/telemetry/test_real_resource_sampler.py \
   tests/runtime_scheduler/test_stepped_loop.py
```

Expected: all six files present, no `No such file` errors.

- [ ] **Confirm git log shows all feature commits**

```bash
git log --oneline -8
```

Expected: seven commits from this plan visible in the log.
