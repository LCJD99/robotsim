# Design Spec: Step-Locked Simulation Loop & Real Resource Sampling

**Date:** 2026-04-22
**Scope:** Batch A gaps — G1 (real-time execution loop) + G5 (real resource sampling)
**Status:** Approved

---

## 1. Problem Statement

Two gaps block a complete, trustworthy experiment trace:

- **G1:** `runtime_scheduler/main.py` drives windows with wall-clock `time.sleep`. Gazebo runs freely and is never synchronized to the scheduler's decision cadence.
- **G5:** `resource_sampler.py` returns all-zero placeholder metrics. Observation data carries no signal.

The goal is a **step-locked loop** where each 50 ms scheduler window drives one explicit Gazebo physics advance, and each observation is backed by real CPU/Memory/GPU/Network measurements.

---

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│              SteppedExperimentLoop                  │
│                                                     │
│  while sim_time < 120s:                             │
│    ① sample  = RealResourceSampler.sample()         │
│    ② obs     = build_observation(sample, window)    │
│    ③ arrivals= PoissonGenerator.next_arrivals()     │
│    ④ plan, outcome = run_single_window(...)         │
│    ⑤ TraceSink.write(obs, plan, outcome, sample)    │
│    ⑥ SimStepper.step(50)   # advance 50 ms sim time │
│                                                     │
└─────────────────────────────────────────────────────┘
         │                        │
         ▼                        ▼
   SimStepper              RealResourceSampler
  (gz-transport)          (cgroup / nvidia-smi / procfs)
  /world/.../control       /sys/fs/cgroup/vee/
```

### New and modified files

| File | Change | Purpose |
|------|--------|---------|
| `src/infra/gazebo/sim_stepper.py` | New | gz-transport WorldControl wrapper |
| `src/infra/gazebo/__init__.py` | New | package marker |
| `src/telemetry/telemetry/real_resource_sampler.py` | New | cgroup / nvidia-smi / procfs sampler |
| `src/runtime_scheduler/runtime_scheduler/stepped_loop.py` | New | step-locked main loop |
| `src/runtime_scheduler/runtime_scheduler/main.py` | Modify | add `run_stepped_experiment()` entry point |
| `src/runtime_scheduler/runtime_scheduler/config.py` | Modify | add `SimConfig` dataclass |
| `src/sim_bringup/launch/sim_stack.launch.py` | Modify | remove `-r` flag; start Gazebo paused |
| `experiment_configs/v1_dynamic_dense.yaml` | Modify | add `sim:` block |
| `tests/telemetry/test_real_resource_sampler.py` | New | unit tests with mock files |
| `tests/runtime_scheduler/test_stepped_loop.py` | New | unit tests with mock stepper/sampler |
| `tests/infra/test_sim_stepper.py` | New | ImportError behaviour without gz-transport |
| `tests/integration/test_sim_stack_config_contract.py` | Modify | assert `sim` block presence |

Existing `run_experiment()`, `run_once_for_test()`, `runtime_loop.py`, `trace_sink.py`, and `resource_sampler.py` are **not modified**. All existing tests continue to pass unchanged.

---

## 3. Component Design

### 3.1 SimStepper

**File:** `src/infra/gazebo/sim_stepper.py`

Wraps gz-transport Python bindings. Raises `ImportError` on construction if `gz.transport` is unavailable so the caller can fallback gracefully.

```python
class SimStepper:
    def __init__(self, world_name: str, physics_step_ms: int = 1) -> None: ...
    def step(self, n_steps: int) -> None: ...
    def sim_time_us(self) -> int: ...
    def close(self) -> None: ...
```

**Behaviour:**

- `step(n_steps)` sends `gz.msgs.WorldControl` to `/world/<world_name>/control` with `step=True` and `multi_step=n_steps`. It then polls `/world/<world_name>/stats` until `sim_time` has advanced by at least `n_steps * physics_step_ms * 1000` µs before returning.
- `sim_time_us()` reads the latest frame from `/world/<world_name>/stats` and returns `sec * 1_000_000 + nsec // 1_000`.
- `close()` releases the gz-transport Node and any active subscriptions.
- `physics_step_ms` defaults to 1 (Gazebo's default 1 kHz physics). The caller computes `n_steps = window_ms // physics_step_ms`.

### 3.2 RealResourceSampler

**File:** `src/telemetry/telemetry/real_resource_sampler.py`

Reads four metric sources independently. Each source has a silent fallback to zero if the path or binary is unavailable, so the sampler runs on development machines without cgroup or GPU.

```python
class RealResourceSampler:
    def __init__(
        self,
        cgroup_root: str = "/sys/fs/cgroup/vee",
        sample_interval_ms: int = 50,
    ) -> None: ...

    def sample(self) -> dict[str, object]: ...
```

**Metric sources:**

| Metric | Source | Method |
|--------|--------|--------|
| CPU utilization | `<cgroup_root>/cpu.stat` field `usage_usec` | delta between consecutive calls ÷ elapsed wall time |
| Memory used / available | `<cgroup_root>/memory.current` and `memory.max` | direct read |
| GPU utilization + memory | `nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader,nounits` | subprocess, timeout 2 s |
| Network TX/RX rate | `/proc/net/dev` bytes columns | delta ÷ elapsed wall time → bps |

**Output schema** is identical to `make_resource_sample()` in `resource_sampler.py` so `TraceSink` requires no changes:

```python
{
    "schema_version": "v1",
    "experiment_id": str,
    "sample_id": str,
    "timestamp_us": int,
    "window_id": str | None,
    "scope": "system",
    "cpu":     {"utilization_total": float},
    "memory":  {"used_bytes": int, "available_bytes": int},
    "gpu":     {"utilization": float, "memory_used_bytes": int},
    "network": {"tx_rate_bps": int, "rx_rate_bps": int},
}
```

`cgroup_root` is overridable via constructor to allow tests to point at a temporary directory of mock files.

### 3.3 SteppedExperimentLoop

**File:** `src/runtime_scheduler/runtime_scheduler/stepped_loop.py`

```python
class SteppedExperimentLoop:
    def __init__(
        self,
        stepper: SimStepper,
        sampler: RealResourceSampler,
        generator: PoissonLocalToolGenerator,
        sink: TraceSink,
        config: Config,
        experiment_id: str,
    ) -> None: ...

    def run(self) -> None: ...
```

**Loop body (one iteration = one 50 ms window):**

```
n_steps      = config.sim.window_ms // config.sim.physics_step_ms   # = 50
duration_us  = config.experiment.duration_sec * 1_000_000           # = 120_000_000

window_idx = 0
while stepper.sim_time_us() < duration_us:
    timestamp_us = stepper.sim_time_us()
    window_id    = f"window-{window_idx + 1}"

    # ① Observe
    raw = sampler.sample()
    resource_record = {
        **raw,
        "experiment_id": experiment_id,
        "sample_id":     f"sample-{window_idx + 1}",
        "timestamp_us":  timestamp_us,
        "window_id":     window_id,
    }

    # ② Task arrivals
    arrivals = generator.next_arrivals(window_id, timestamp_us)
    tasks    = [{"task_id": a["task_id"], "priority_class": "ELASTIC"} for a in arrivals]
    for arrival in arrivals:
        sink.write("task_events", build_task_event(experiment_id, arrival))

    # ③ Schedule
    observation, plan, outcome = run_single_window(window_id, timestamp_us, tasks)

    # ④ Trace
    sink.write("window_observation", observation)
    sink.write("plan",               plan)
    sink.write("outcome",            outcome)
    sink.write("resource_samples",   resource_record)

    # ⑤ Advance sim
    stepper.step(n_steps)
    window_idx += 1
```

Exit is automatic when `sim_time_us() >= duration_us`. No signal handling required for normal termination.

### 3.4 main.py — new entry point

```python
def run_stepped_experiment(output_root: Path, config: Config) -> None:
    from infra.gazebo.sim_stepper import SimStepper
    experiment_id = make_experiment_id()
    stepper  = SimStepper(config.sim.world_name, config.sim.physics_step_ms)
    sampler  = RealResourceSampler(sample_interval_ms=config.scheduler.window_ms)
    sink     = TraceSink(root_dir=output_root, experiment_id=experiment_id)
    generator = PoissonLocalToolGenerator(...)
    loop = SteppedExperimentLoop(stepper, sampler, generator, sink, config, experiment_id)
    try:
        loop.run()
    finally:
        stepper.close()


def main() -> None:
    config = load_config(CONFIG_PATH)
    try:
        run_stepped_experiment(output_root=config.trace.root_dir, config=config)
    except ImportError:
        import warnings
        warnings.warn("gz-transport unavailable; falling back to wall-clock run_experiment()")
        run_experiment(output_root=config.trace.root_dir, config=config)
```

---

## 4. Configuration Changes

### `experiment_configs/v1_dynamic_dense.yaml` — new `sim` block

```yaml
sim:
  world_name: dynamic_obstacle_dense
  physics_step_ms: 1          # Gazebo default physics rate (1 kHz)
```

### `config.py` — new dataclass

```python
@dataclass(frozen=True)
class SimConfig:
    world_name: str = "dynamic_obstacle_dense"
    physics_step_ms: int = 1

@dataclass(frozen=True)
class Config:
    ...
    sim: SimConfig = field(default_factory=SimConfig)
```

`load_config()` reads the optional `sim:` key; missing key uses `SimConfig()` defaults for backward compatibility with existing YAML files and tests.

---

## 5. Launch Change

**`src/sim_bringup/launch/sim_stack.launch.py`**

```python
# Before
"gz_args": ["-r -s ", world]

# After
"gz_args": ["-s ", world]     # start paused; SteppedExperimentLoop drives stepping
```

Gazebo starts in server mode, paused. The scheduler loop calls `SimStepper.step()` to advance the simulation. This ensures every physics advance is preceded by a complete Observation → Plan cycle.

---

## 6. Testing

All tests use mocks and do not require a running Gazebo instance, cgroup filesystem, or GPU.

### `tests/telemetry/test_real_resource_sampler.py`
- Write mock `cpu.stat`, `memory.current`, `memory.max` files to a `tmp_path` directory; pass as `cgroup_root`.
- Mock `subprocess.run` to return a fixed `nvidia-smi` CSV string.
- Assert delta CPU and network calculations are correct across two consecutive `sample()` calls.
- Assert all fields fall back to zero when paths are absent.

### `tests/runtime_scheduler/test_stepped_loop.py`
- `MockStepper`: `sim_time_us()` increments by `window_ms * 1000` on each call; `step()` is a no-op.
- `MockSampler`: returns a fixed all-zero resource dict.
- Assert loop exits after exactly `duration_sec * 1000 / window_ms` iterations.
- Assert `TraceSink` receives one `resource_samples` record and one `plan` record per iteration.

### `tests/infra/test_sim_stepper.py`
- Patch `gz.transport` to be unimportable via `sys.modules`.
- Assert `SimStepper(...)` raises `ImportError`.

### `tests/integration/test_sim_stack_config_contract.py` (extend existing)
- Assert `v1_dynamic_dense.yaml` contains top-level key `sim`.
- Assert `sim.world_name` is a non-empty string.
- Assert `sim.physics_step_ms` is a positive integer.

---

## 7. Non-Goals (out of scope for this spec)

- G2 (Execution Adapter: `/cmd_vel` publishing, vee process control)
- G3 (Worker physical load: real CPU/GPU-consuming worker processes)
- G4 (VEE auto-mount: PID discovery and cgroup injection at startup)

These are deferred to Batch B.
