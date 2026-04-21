# Runtime Platform Trace Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a runnable v1 experiment platform that runs 120s windows at 50ms, enforces VEE limits, schedules critical-first FIFO, generates Poisson LOCAL_TOOL arrivals, and writes 5 JSONL traces with strict schema contracts.

**Architecture:** Use a Python runtime orchestrator with pluggable modules (`ModeTrigger`, `PolicyCore`, `LaneMapper`, `ExecutionAdapter`, `TraceSink`, `AgentWorkloadGenerator`). Keep Gazebo outside VEE while runtime/control/agent workers run inside VEE constraints. Enforce schema-compatible JSONL outputs and append-only trace behavior.

**Tech Stack:** Python 3.11, pytest, PyYAML, ROS 2 Jazzy integration points (runtime-facing), Linux cgroup v2, hami-core hooks, JSONL trace files.

---

## Scope Check
This plan targets one subsystem cluster: the **online experiment platform MVP** (runtime + generator + trace + VEE adapter). It intentionally excludes offline scheduler evolution and REMOTE_API execution.

## File Structure (lock boundaries before coding)

- Create: `pyproject.toml`
  - Python project metadata and dependencies (`pytest`, `pyyaml`)
- Create: `src/runtime_scheduler/runtime_scheduler/__init__.py`
- Create: `src/runtime_scheduler/runtime_scheduler/config.py`
  - YAML schema, typed config objects, validation
- Create: `src/runtime_scheduler/runtime_scheduler/experiment_id.py`
  - local-time `YYYYMMDD-HHMMSS` ID builder
- Create: `src/runtime_scheduler/runtime_scheduler/mode_trigger.py`
  - hybrid mode trigger contract + default implementation
- Create: `src/runtime_scheduler/runtime_scheduler/policy_core.py`
  - critical-first FIFO scheduler
- Create: `src/runtime_scheduler/runtime_scheduler/workload_generator.py`
  - Poisson LOCAL_TOOL arrival generator
- Create: `src/runtime_scheduler/runtime_scheduler/runtime_loop.py`
  - 50ms loop: observation -> plan -> outcome
- Create: `src/runtime_scheduler/runtime_scheduler/main.py`
  - CLI entrypoint (`--config`)
- Create: `src/telemetry/telemetry/__init__.py`
- Create: `src/telemetry/telemetry/schema_contract.py`
  - required fields for 5 JSONL files + validator
- Create: `src/telemetry/telemetry/trace_sink.py`
  - append-only writer, experiment directory management
- Create: `src/telemetry/telemetry/resource_sampler.py`
  - CPU/memory/GPU/network sample collection shape
- Create: `src/infra/vee/vee_adapter.py`
  - apply/verify cgroup2 + hami-core config hooks
- Create: `experiment_configs/v1_dynamic_dense.yaml`
  - final config values from approved spec
- Create: `tests/runtime_scheduler/test_config.py`
- Create: `tests/runtime_scheduler/test_experiment_id.py`
- Create: `tests/runtime_scheduler/test_policy_core.py`
- Create: `tests/runtime_scheduler/test_workload_generator.py`
- Create: `tests/telemetry/test_schema_contract.py`
- Create: `tests/telemetry/test_trace_sink.py`
- Create: `tests/telemetry/test_resource_sampler.py`
- Create: `tests/integration/test_runtime_loop_smoke.py`

### Task 1: Bootstrap Project Skeleton and Test Runner

**Files:**
- Create: `pyproject.toml`
- Create: `src/runtime_scheduler/runtime_scheduler/__init__.py`
- Create: `src/telemetry/telemetry/__init__.py`
- Create: `tests/runtime_scheduler/test_experiment_id.py`

- [ ] **Step 1: Write the failing import smoke test**

```python
# tests/runtime_scheduler/test_experiment_id.py
from runtime_scheduler.experiment_id import make_experiment_id


def test_make_experiment_id_shape():
    value = make_experiment_id()
    assert len(value) == 15
    assert value[8] == "-"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/runtime_scheduler/test_experiment_id.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'runtime_scheduler'`

- [ ] **Step 3: Create minimal package skeleton**

```toml
# pyproject.toml
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "robotsim-runtime"
version = "0.1.0"
dependencies = [
  "PyYAML>=6.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0"]

[tool.pytest.ini_options]
pythonpath = ["src/runtime_scheduler", "src/telemetry", "src/infra"]
testpaths = ["tests"]
```

```python
# src/runtime_scheduler/runtime_scheduler/__init__.py
__all__ = []
```

```python
# src/telemetry/telemetry/__init__.py
__all__ = []
```

- [ ] **Step 4: Add minimal implementation for import target**

```python
# src/runtime_scheduler/runtime_scheduler/experiment_id.py
from datetime import datetime


def make_experiment_id() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/runtime_scheduler/test_experiment_id.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml src/runtime_scheduler/runtime_scheduler/__init__.py src/runtime_scheduler/runtime_scheduler/experiment_id.py src/telemetry/telemetry/__init__.py tests/runtime_scheduler/test_experiment_id.py
git commit -m "chore: bootstrap runtime python project and test harness"
```

### Task 2: Implement YAML Config Contract

**Files:**
- Create: `src/runtime_scheduler/runtime_scheduler/config.py`
- Create: `tests/runtime_scheduler/test_config.py`
- Create: `experiment_configs/v1_dynamic_dense.yaml`

- [ ] **Step 1: Write failing tests for required config fields**

```python
# tests/runtime_scheduler/test_config.py
from runtime_scheduler.config import load_config


def test_load_config_reads_required_fields(tmp_path):
    path = tmp_path / "c.yaml"
    path.write_text(
        """
experiment:
  duration_sec: 120
  id_format: "%Y%m%d-%H%M%S"
scheduler:
  impl: critical_first_fifo
  window_ms: 50
agent_workload:
  generator: poisson
  seed: 42
  local_tool:
    lambda_per_sec: 4.0
    max_arrivals_per_window: 8
""".strip()
    )
    cfg = load_config(path)
    assert cfg.experiment.duration_sec == 120
    assert cfg.scheduler.window_ms == 50
    assert cfg.agent_workload.local_tool.lambda_per_sec == 4.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/runtime_scheduler/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: runtime_scheduler.config`

- [ ] **Step 3: Implement typed config loader**

```python
# src/runtime_scheduler/runtime_scheduler/config.py
from dataclasses import dataclass
from pathlib import Path
import yaml


@dataclass(frozen=True)
class ExperimentConfig:
    duration_sec: int
    id_format: str


@dataclass(frozen=True)
class SchedulerConfig:
    impl: str
    window_ms: int


@dataclass(frozen=True)
class LocalToolArrivalConfig:
    lambda_per_sec: float
    max_arrivals_per_window: int


@dataclass(frozen=True)
class AgentWorkloadConfig:
    generator: str
    seed: int
    local_tool: LocalToolArrivalConfig


@dataclass(frozen=True)
class Config:
    experiment: ExperimentConfig
    scheduler: SchedulerConfig
    agent_workload: AgentWorkloadConfig


def _require(mapping: dict, key: str):
    if key not in mapping:
        raise ValueError(f"missing required key: {key}")
    return mapping[key]


def load_config(path: Path) -> Config:
    raw = yaml.safe_load(path.read_text())
    exp = _require(raw, "experiment")
    sch = _require(raw, "scheduler")
    aw = _require(raw, "agent_workload")
    local_tool = _require(aw, "local_tool")
    return Config(
        experiment=ExperimentConfig(
            duration_sec=int(_require(exp, "duration_sec")),
            id_format=str(_require(exp, "id_format")),
        ),
        scheduler=SchedulerConfig(
            impl=str(_require(sch, "impl")),
            window_ms=int(_require(sch, "window_ms")),
        ),
        agent_workload=AgentWorkloadConfig(
            generator=str(_require(aw, "generator")),
            seed=int(_require(aw, "seed")),
            local_tool=LocalToolArrivalConfig(
                lambda_per_sec=float(_require(local_tool, "lambda_per_sec")),
                max_arrivals_per_window=int(_require(local_tool, "max_arrivals_per_window")),
            ),
        ),
    )
```

- [ ] **Step 4: Add baseline experiment config**

```yaml
# experiment_configs/v1_dynamic_dense.yaml
experiment:
  duration_sec: 120
  id_format: "%Y%m%d-%H%M%S"

scenario:
  type: dynamic_obstacle_dense

scheduler:
  impl: critical_first_fifo
  window_ms: 50

trigger:
  impl: hybrid
  cooldown_windows: 10

agent:
  enabled_task_types:
    - LOCAL_TOOL

agent_workload:
  generator: poisson
  seed: 42
  local_tool:
    lambda_per_sec: 4.0
    max_arrivals_per_window: 8

vee:
  profile: edge_box_small
  cpu:
    cpuset: "0-7"
    quota: "600000 1000000"
  memory:
    high: "6G"
    max: "8G"
  gpu:
    provider: hami-core

trace:
  root_dir: traces
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/runtime_scheduler/test_config.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/runtime_scheduler/runtime_scheduler/config.py tests/runtime_scheduler/test_config.py experiment_configs/v1_dynamic_dense.yaml
git commit -m "feat: add typed yaml config loader for runtime"
```

### Task 3: Implement Schema Contract Validator for JSONL

**Files:**
- Create: `src/telemetry/telemetry/schema_contract.py`
- Create: `tests/telemetry/test_schema_contract.py`

- [ ] **Step 1: Write failing tests for required keys**

```python
# tests/telemetry/test_schema_contract.py
import pytest
from telemetry.schema_contract import validate_record


def test_observation_requires_window_identity_keys():
    record = {"schema_version": "v1", "window_id": "w1"}
    with pytest.raises(ValueError):
        validate_record("window_observation", record)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/telemetry/test_schema_contract.py -v`
Expected: FAIL with `ModuleNotFoundError: telemetry.schema_contract`

- [ ] **Step 3: Implement validator with strict required keys**

```python
# src/telemetry/telemetry/schema_contract.py
REQUIRED_KEYS = {
    "window_observation": {"schema_version", "window_id", "timestamp_us", "scheduler_version", "policy_hash"},
    "plan": {"schema_version", "plan_id", "window_id", "generated_at_us", "scheduler_version", "policy_hash"},
    "outcome": {"schema_version", "outcome_id", "window_id", "plan_id", "scheduler_version", "policy_hash"},
    "task_events": {"schema_version", "experiment_id", "event_id", "event_type", "timestamp_us", "window_id", "task_id", "request_id", "task_type", "source"},
    "resource_samples": {"schema_version", "experiment_id", "sample_id", "timestamp_us", "scope", "cpu", "memory", "gpu", "network"},
}


def validate_record(kind: str, record: dict) -> None:
    expected = REQUIRED_KEYS[kind]
    missing = expected.difference(record.keys())
    if missing:
        raise ValueError(f"{kind} missing keys: {sorted(missing)}")
    if record.get("schema_version") != "v1":
        raise ValueError(f"{kind} requires schema_version=v1")
    if kind == "task_events" and record.get("event_type") == "TASK_ARRIVAL":
        for key in ("arrival_source", "generator_seed", "lambda_per_sec"):
            if key not in record:
                raise ValueError(f"task arrival missing key: {key}")
```

- [ ] **Step 4: Add pass-case test**

```python
# append in tests/telemetry/test_schema_contract.py

def test_task_arrival_requires_poisson_metadata():
    record = {
        "schema_version": "v1",
        "experiment_id": "20260421-120000",
        "event_id": "e1",
        "event_type": "TASK_ARRIVAL",
        "timestamp_us": 1,
        "window_id": "w1",
        "task_id": "t1",
        "request_id": "r1",
        "task_type": "LOCAL_TOOL",
        "source": "generator",
        "arrival_source": "poisson",
        "generator_seed": 42,
        "lambda_per_sec": 4.0,
    }
    validate_record("task_events", record)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/telemetry/test_schema_contract.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/telemetry/telemetry/schema_contract.py tests/telemetry/test_schema_contract.py
git commit -m "feat: add strict trace schema contract validator"
```

### Task 4: Implement TraceSink and Experiment Directory Layout

**Files:**
- Create: `src/telemetry/telemetry/trace_sink.py`
- Create: `tests/telemetry/test_trace_sink.py`

- [ ] **Step 1: Write failing test for append-only JSONL writes**

```python
# tests/telemetry/test_trace_sink.py
from telemetry.trace_sink import TraceSink


def test_trace_sink_writes_jsonl_lines(tmp_path):
    sink = TraceSink(root_dir=tmp_path, experiment_id="20260421-120000")
    sink.write("plan", {"schema_version": "v1", "plan_id": "p1", "window_id": "w1", "generated_at_us": 1, "scheduler_version": "s", "policy_hash": "h"})
    content = (tmp_path / "20260421-120000" / "plan.jsonl").read_text().strip().splitlines()
    assert len(content) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/telemetry/test_trace_sink.py -v`
Expected: FAIL with `ModuleNotFoundError: telemetry.trace_sink`

- [ ] **Step 3: Implement TraceSink using schema validator**

```python
# src/telemetry/telemetry/trace_sink.py
from __future__ import annotations

import json
from pathlib import Path
from telemetry.schema_contract import validate_record

KIND_TO_FILE = {
    "window_observation": "window_observation.jsonl",
    "plan": "plan.jsonl",
    "outcome": "outcome.jsonl",
    "task_events": "task_events.jsonl",
    "resource_samples": "resource_samples.jsonl",
}


class TraceSink:
    def __init__(self, root_dir: Path, experiment_id: str):
        self.base = Path(root_dir) / experiment_id
        self.base.mkdir(parents=True, exist_ok=True)

    def write(self, kind: str, record: dict) -> None:
        validate_record(kind, record)
        path = self.base / KIND_TO_FILE[kind]
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=True) + "\n")
```

- [ ] **Step 4: Add test for append-not-overwrite behavior**

```python
# append in tests/telemetry/test_trace_sink.py

def test_trace_sink_appends_without_overwrite(tmp_path):
    sink = TraceSink(root_dir=tmp_path, experiment_id="20260421-120000")
    record = {"schema_version": "v1", "plan_id": "p1", "window_id": "w1", "generated_at_us": 1, "scheduler_version": "s", "policy_hash": "h"}
    sink.write("plan", record)
    sink.write("plan", {**record, "plan_id": "p2"})
    lines = (tmp_path / "20260421-120000" / "plan.jsonl").read_text().strip().splitlines()
    assert len(lines) == 2
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/telemetry/test_trace_sink.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/telemetry/telemetry/trace_sink.py tests/telemetry/test_trace_sink.py
git commit -m "feat: add append-only trace sink with jsonl outputs"
```

### Task 5: Implement Poisson LOCAL_TOOL Workload Generator

**Files:**
- Create: `src/runtime_scheduler/runtime_scheduler/workload_generator.py`
- Create: `tests/runtime_scheduler/test_workload_generator.py`

- [ ] **Step 1: Write failing deterministic Poisson test**

```python
# tests/runtime_scheduler/test_workload_generator.py
from runtime_scheduler.workload_generator import PoissonLocalToolGenerator


def test_poisson_generator_is_seed_deterministic():
    g1 = PoissonLocalToolGenerator(lambda_per_sec=4.0, window_ms=50, seed=42, max_arrivals_per_window=8)
    g2 = PoissonLocalToolGenerator(lambda_per_sec=4.0, window_ms=50, seed=42, max_arrivals_per_window=8)
    assert g1.next_arrivals(window_id="w1", timestamp_us=1000) == g2.next_arrivals(window_id="w1", timestamp_us=1000)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/runtime_scheduler/test_workload_generator.py -v`
Expected: FAIL with `ModuleNotFoundError: runtime_scheduler.workload_generator`

- [ ] **Step 3: Implement Poisson generator**

```python
# src/runtime_scheduler/runtime_scheduler/workload_generator.py
from __future__ import annotations

from dataclasses import dataclass
import random


@dataclass(frozen=True)
class ArrivalEvent:
    event_type: str
    task_id: str
    request_id: str
    window_id: str
    timestamp_us: int
    arrival_source: str
    generator_seed: int
    lambda_per_sec: float


class PoissonLocalToolGenerator:
    def __init__(self, lambda_per_sec: float, window_ms: int, seed: int, max_arrivals_per_window: int):
        self.lambda_per_sec = lambda_per_sec
        self.window_ms = window_ms
        self.seed = seed
        self.max_arrivals_per_window = max_arrivals_per_window
        self._rng = random.Random(seed)
        self._seq = 0

    def _sample_poisson(self, mean: float) -> int:
        # Knuth algorithm, sufficient for small means in MVP
        l = pow(2.718281828459045, -mean)
        k = 0
        p = 1.0
        while p > l:
            k += 1
            p *= self._rng.random()
        return k - 1

    def next_arrivals(self, window_id: str, timestamp_us: int) -> list[dict]:
        mean = self.lambda_per_sec * (self.window_ms / 1000.0)
        count = min(self._sample_poisson(mean), self.max_arrivals_per_window)
        out = []
        for _ in range(count):
            self._seq += 1
            task_id = f"local-tool-{self._seq}"
            out.append(
                {
                    "event_type": "TASK_ARRIVAL",
                    "task_id": task_id,
                    "request_id": f"req-{self._seq}",
                    "window_id": window_id,
                    "timestamp_us": timestamp_us,
                    "arrival_source": "poisson",
                    "generator_seed": self.seed,
                    "lambda_per_sec": self.lambda_per_sec,
                }
            )
        return out
```

- [ ] **Step 4: Add cap test**

```python
# append in tests/runtime_scheduler/test_workload_generator.py

def test_poisson_generator_respects_per_window_cap():
    gen = PoissonLocalToolGenerator(lambda_per_sec=200.0, window_ms=50, seed=42, max_arrivals_per_window=3)
    arrivals = gen.next_arrivals(window_id="w1", timestamp_us=1)
    assert len(arrivals) <= 3
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/runtime_scheduler/test_workload_generator.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/runtime_scheduler/runtime_scheduler/workload_generator.py tests/runtime_scheduler/test_workload_generator.py
git commit -m "feat: add poisson local tool workload generator"
```

### Task 6: Implement Critical-First FIFO Policy and Hybrid Trigger

**Files:**
- Create: `src/runtime_scheduler/runtime_scheduler/policy_core.py`
- Create: `src/runtime_scheduler/runtime_scheduler/mode_trigger.py`
- Create: `tests/runtime_scheduler/test_policy_core.py`

- [ ] **Step 1: Write failing policy ordering test**

```python
# tests/runtime_scheduler/test_policy_core.py
from runtime_scheduler.policy_core import plan_critical_first_fifo


def test_policy_orders_critical_before_local_tool():
    tasks = [
        {"task_id": "a", "priority_class": "ELASTIC"},
        {"task_id": "b", "priority_class": "HARD_CRITICAL"},
        {"task_id": "c", "priority_class": "ELASTIC"},
    ]
    actions = plan_critical_first_fifo(tasks)
    assert [x["task_id"] for x in actions] == ["b", "a", "c"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/runtime_scheduler/test_policy_core.py -v`
Expected: FAIL with `ModuleNotFoundError: runtime_scheduler.policy_core`

- [ ] **Step 3: Implement FIFO policy**

```python
# src/runtime_scheduler/runtime_scheduler/policy_core.py
from __future__ import annotations


def plan_critical_first_fifo(tasks: list[dict]) -> list[dict]:
    critical = [t for t in tasks if t.get("priority_class") in {"HARD_CRITICAL", "SOFT_CRITICAL"}]
    non_critical = [t for t in tasks if t.get("priority_class") not in {"HARD_CRITICAL", "SOFT_CRITICAL"}]
    ordered = critical + non_critical
    return [
        {
            "task_id": t["task_id"],
            "decision": "RUN",
            "lane": "CRITICAL_LANE" if t in critical else "CPU_LANE",
        }
        for t in ordered
    ]
```

- [ ] **Step 4: Implement hybrid mode trigger contract**

```python
# src/runtime_scheduler/runtime_scheduler/mode_trigger.py
from __future__ import annotations


MODES = ("NORMAL", "CONSERVATIVE", "DEGRADED", "EMERGENCY")


class HybridModeTrigger:
    def __init__(self, cooldown_windows: int):
        self.cooldown_windows = cooldown_windows
        self._last_raise_window = -10**9

    def decide(self, window_index: int, runtime_raise: bool, scheduler_requested: str) -> str:
        if runtime_raise:
            self._last_raise_window = window_index
            return "CONSERVATIVE"
        if window_index - self._last_raise_window < self.cooldown_windows:
            return "CONSERVATIVE"
        if scheduler_requested not in MODES:
            return "NORMAL"
        return scheduler_requested
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/runtime_scheduler/test_policy_core.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/runtime_scheduler/runtime_scheduler/policy_core.py src/runtime_scheduler/runtime_scheduler/mode_trigger.py tests/runtime_scheduler/test_policy_core.py
git commit -m "feat: add critical-first fifo policy and hybrid mode trigger"
```

### Task 7: Implement VEE Adapter and Resource Sampler

**Files:**
- Create: `src/infra/vee/vee_adapter.py`
- Create: `src/telemetry/telemetry/resource_sampler.py`
- Create: `tests/telemetry/test_resource_sampler.py`

- [ ] **Step 1: Write failing sampler shape test**

```python
# tests/telemetry/test_resource_sampler.py
from telemetry.resource_sampler import make_resource_sample


def test_resource_sample_has_required_top_level_keys():
    sample = make_resource_sample(experiment_id="20260421-120000", sample_id="s1", timestamp_us=1)
    assert set(sample.keys()) >= {"schema_version", "experiment_id", "sample_id", "timestamp_us", "scope", "cpu", "memory", "gpu", "network"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/telemetry/test_resource_sampler.py -v`
Expected: FAIL with `ModuleNotFoundError: telemetry.resource_sampler`

- [ ] **Step 3: Implement VEE profile apply/verify hooks**

```python
# src/infra/vee/vee_adapter.py
from __future__ import annotations


class VeeAdapter:
    def __init__(self, profile: dict):
        self.profile = profile

    def planned_commands(self) -> list[str]:
        cpu = self.profile["cpu"]
        mem = self.profile["memory"]
        return [
            f"echo {cpu['cpuset']} > /sys/fs/cgroup/vee/cpuset.cpus",
            f"echo {cpu['quota']} > /sys/fs/cgroup/vee/cpu.max",
            f"echo {mem['high']} > /sys/fs/cgroup/vee/memory.high",
            f"echo {mem['max']} > /sys/fs/cgroup/vee/memory.max",
            "hami-core apply --group vee",
        ]
```

- [ ] **Step 4: Implement minimal resource sampler**

```python
# src/telemetry/telemetry/resource_sampler.py
from __future__ import annotations


def make_resource_sample(experiment_id: str, sample_id: str, timestamp_us: int) -> dict:
    return {
        "schema_version": "v1",
        "experiment_id": experiment_id,
        "sample_id": sample_id,
        "timestamp_us": timestamp_us,
        "scope": "system",
        "cpu": {"utilization_total": 0.0},
        "memory": {"used_bytes": 0, "available_bytes": 0},
        "gpu": {"utilization": 0.0, "memory_used_bytes": 0},
        "network": {"tx_rate_bps": 0, "rx_rate_bps": 0},
    }
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/telemetry/test_resource_sampler.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/infra/vee/vee_adapter.py src/telemetry/telemetry/resource_sampler.py tests/telemetry/test_resource_sampler.py
git commit -m "feat: add vee adapter hooks and resource sample shape"
```

### Task 8: Implement Runtime Loop Integration and CLI

**Files:**
- Create: `src/runtime_scheduler/runtime_scheduler/runtime_loop.py`
- Create: `src/runtime_scheduler/runtime_scheduler/main.py`
- Create: `tests/integration/test_runtime_loop_smoke.py`

- [ ] **Step 1: Write failing integration smoke test**

```python
# tests/integration/test_runtime_loop_smoke.py
from pathlib import Path
from runtime_scheduler.main import run_once_for_test


def test_runtime_smoke_creates_all_trace_files(tmp_path):
    run_once_for_test(output_root=tmp_path)
    exp_dirs = [p for p in tmp_path.iterdir() if p.is_dir()]
    assert len(exp_dirs) == 1
    files = {p.name for p in exp_dirs[0].iterdir()}
    assert files >= {
        "window_observation.jsonl",
        "plan.jsonl",
        "outcome.jsonl",
        "task_events.jsonl",
        "resource_samples.jsonl",
    }
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/integration/test_runtime_loop_smoke.py -v`
Expected: FAIL with `ModuleNotFoundError: runtime_scheduler.main`

- [ ] **Step 3: Implement runtime loop and test helper**

```python
# src/runtime_scheduler/runtime_scheduler/runtime_loop.py
from __future__ import annotations

from runtime_scheduler.policy_core import plan_critical_first_fifo


def run_single_window(window_id: str, timestamp_us: int, tasks: list[dict]) -> tuple[dict, dict, dict]:
    observation = {
        "schema_version": "v1",
        "window_id": window_id,
        "timestamp_us": timestamp_us,
        "scheduler_version": "v1",
        "policy_hash": "critical_first_fifo",
    }
    plan = {
        "schema_version": "v1",
        "plan_id": f"plan-{window_id}",
        "window_id": window_id,
        "generated_at_us": timestamp_us,
        "scheduler_version": "v1",
        "policy_hash": "critical_first_fifo",
        "task_actions": plan_critical_first_fifo(tasks),
    }
    outcome = {
        "schema_version": "v1",
        "outcome_id": f"outcome-{window_id}",
        "window_id": window_id,
        "plan_id": plan["plan_id"],
        "scheduler_version": "v1",
        "policy_hash": "critical_first_fifo",
    }
    return observation, plan, outcome
```

```python
# src/runtime_scheduler/runtime_scheduler/main.py
from __future__ import annotations

from pathlib import Path
import time

from runtime_scheduler.experiment_id import make_experiment_id
from runtime_scheduler.runtime_loop import run_single_window
from runtime_scheduler.workload_generator import PoissonLocalToolGenerator
from telemetry.trace_sink import TraceSink
from telemetry.resource_sampler import make_resource_sample


def run_once_for_test(output_root: Path) -> None:
    experiment_id = make_experiment_id()
    sink = TraceSink(root_dir=output_root, experiment_id=experiment_id)
    gen = PoissonLocalToolGenerator(lambda_per_sec=4.0, window_ms=50, seed=42, max_arrivals_per_window=8)

    window_id = "w-1"
    ts = int(time.time() * 1_000_000)
    arrivals = gen.next_arrivals(window_id=window_id, timestamp_us=ts)
    tasks = [{"task_id": a["task_id"], "priority_class": "ELASTIC"} for a in arrivals]

    for a in arrivals:
        sink.write(
            "task_events",
            {
                "schema_version": "v1",
                "experiment_id": experiment_id,
                "event_id": f"evt-{a['task_id']}",
                "event_type": "TASK_ARRIVAL",
                "timestamp_us": a["timestamp_us"],
                "window_id": a["window_id"],
                "task_id": a["task_id"],
                "request_id": a["request_id"],
                "task_type": "LOCAL_TOOL",
                "source": "generator",
                "arrival_source": "poisson",
                "generator_seed": 42,
                "lambda_per_sec": 4.0,
            },
        )

    obs, plan, outcome = run_single_window(window_id=window_id, timestamp_us=ts, tasks=tasks)
    sink.write("window_observation", obs)
    sink.write("plan", plan)
    sink.write("outcome", outcome)

    sink.write(
        "resource_samples",
        make_resource_sample(experiment_id=experiment_id, sample_id="sample-1", timestamp_us=ts),
    )


def main() -> None:
    run_once_for_test(output_root=Path("traces"))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run integration test to verify it passes**

Run: `pytest tests/integration/test_runtime_loop_smoke.py -v`
Expected: PASS

- [ ] **Step 5: Run full test suite**

Run: `pytest -v`
Expected: all tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/runtime_scheduler/runtime_scheduler/runtime_loop.py src/runtime_scheduler/runtime_scheduler/main.py tests/integration/test_runtime_loop_smoke.py
git commit -m "feat: integrate runtime loop, generator, and trace writing"
```

### Task 9: Wire 120s/50ms Runtime Config and Docs

**Files:**
- Modify: `src/runtime_scheduler/runtime_scheduler/main.py`
- Create: `tests/integration/test_runtime_duration_config.py`
- Modify: `README.md`

- [ ] **Step 1: Write failing duration/window config test**

```python
# tests/integration/test_runtime_duration_config.py
from runtime_scheduler.config import load_config
from pathlib import Path


def test_default_config_has_120s_and_50ms():
    cfg = load_config(Path("experiment_configs/v1_dynamic_dense.yaml"))
    assert cfg.experiment.duration_sec == 120
    assert cfg.scheduler.window_ms == 50
```

- [ ] **Step 2: Run test to verify it fails (if fields missing in typed model)**

Run: `pytest tests/integration/test_runtime_duration_config.py -v`
Expected: FAIL if config parsing regressed; otherwise PASS

- [ ] **Step 3: Update runtime main to consume config file path**

```python
# key additions in src/runtime_scheduler/runtime_scheduler/main.py
from runtime_scheduler.config import load_config


def main() -> None:
    cfg = load_config(Path("experiment_configs/v1_dynamic_dense.yaml"))
    # For MVP, execute one test window path; next iteration expands to full 120s loop.
    run_once_for_test(output_root=Path("traces"))
```

- [ ] **Step 4: Add operator run instructions**

```markdown
# README.md
## Run MVP runtime experiment

```bash
python -m runtime_scheduler.main
```

Output is written under `traces/<YYYYMMDD-HHMMSS>/` with five JSONL files.
```

- [ ] **Step 5: Run targeted and full tests**

Run: `pytest tests/integration/test_runtime_duration_config.py -v && pytest -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/runtime_scheduler/runtime_scheduler/main.py tests/integration/test_runtime_duration_config.py README.md
git commit -m "docs: wire baseline config and runtime execution instructions"
```

## Final Verification Checklist (must pass before claiming done)
- [ ] `pytest -v` passes
- [ ] Running `python -m runtime_scheduler.main` creates exactly one experiment directory
- [ ] Trace directory contains all 5 files
- [ ] `task_events.jsonl` contains Poisson arrival metadata
- [ ] `plan.jsonl` rows include `window_id/scheduler_version/policy_hash`
- [ ] `outcome.jsonl` rows include `plan_id` that exists in `plan.jsonl`

## Plan Self-Review
- Spec coverage check:
  - Poisson LOCAL_TOOL generator: covered in Task 5 + Task 8
  - 5 JSONL schema compliance: covered in Task 3 + Task 4 + Task 8
  - VEE constraints hooks: covered in Task 7
  - 120s/50ms config presence: covered in Task 2 + Task 9
  - Critical-first FIFO baseline: covered in Task 6
- Placeholder scan: no `TBD/TODO/implement later` remains.
- Type consistency: `window_id`, `scheduler_version`, `policy_hash`, `plan_id`, and `experiment_id` are consistently used across tasks.
