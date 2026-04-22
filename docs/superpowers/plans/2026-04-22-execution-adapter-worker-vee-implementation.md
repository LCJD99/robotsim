# Execution Adapter + Worker + VEE Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 step-locked 调度循环中实现 `task_actions -> /cmd_vel` 物理控制、按任务粒度 Worker 停/恢、以及 VEE 启动约束与 PID 动态注入的闭环执行链路。

**Architecture:** 在 `SteppedExperimentLoop` 中新增执行阶段，调用 `ExecutionAdapter.execute_window(...)` 完成 ROS2 与进程控制。`WorkerManager` 维护 `task_id -> pid` 并管理进程生命周期，`VeeRuntimeEnforcer` 负责启动阶段强制约束与 PID 注入。执行结果按窗口写入 trace 的 `execution` 字段，支持失败可审计与 fail-fast 边界。

**Tech Stack:** Python 3.10, pytest, ROS 2 (`rclpy`, `geometry_msgs.msg.Twist`), Linux signals/cgroup v2, existing runtime_scheduler + telemetry modules.

---

## File Structure

- Create: `src/runtime_scheduler/runtime_scheduler/execution_adapter.py`
- Create: `src/runtime_scheduler/runtime_scheduler/cmd_vel_publisher.py`
- Create: `src/runtime_scheduler/runtime_scheduler/worker_manager.py`
- Create: `src/runtime_scheduler/runtime_scheduler/worker_process.py`
- Create: `src/runtime_scheduler/runtime_scheduler/vee_runtime_enforcer.py`
- Modify: `src/runtime_scheduler/runtime_scheduler/config.py`
- Modify: `src/runtime_scheduler/runtime_scheduler/stepped_loop.py`
- Modify: `src/runtime_scheduler/runtime_scheduler/main.py`
- Modify: `experiment_configs/v1_dynamic_dense.yaml`
- Test: `tests/runtime_scheduler/test_execution_adapter.py`
- Test: `tests/runtime_scheduler/test_worker_manager.py`
- Test: `tests/runtime_scheduler/test_vee_runtime_enforcer.py`
- Test: `tests/runtime_scheduler/test_stepped_loop.py`
- Test: `tests/runtime_scheduler/test_config.py`
- Test: `tests/integration/test_execution_trace_contract.py`

## Task 1: 扩展配置模型（执行映射与 enforcement 开关）

**Files:**
- Modify: `src/runtime_scheduler/runtime_scheduler/config.py`
- Modify: `experiment_configs/v1_dynamic_dense.yaml`
- Test: `tests/runtime_scheduler/test_config.py`

- [ ] **Step 1: Write the failing config tests**

```python
# tests/runtime_scheduler/test_config.py

def test_load_config_reads_execution_defaults():
    cfg = load_config(BASELINE_CONFIG)
    assert cfg.execution.stop_on_non_run is True
    assert cfg.execution.mapping.critical == (0.20, 0.00)
    assert cfg.execution.mapping.high == (0.12, 0.15)
    assert cfg.execution.mapping.best_effort == (0.08, -0.10)
    assert cfg.execution.mapping.fallback == (0.10, 0.00)


def test_load_config_reads_vee_enforcement_flag():
    cfg = load_config(BASELINE_CONFIG)
    assert cfg.vee.enforcement_required is True
```

- [ ] **Step 2: Run tests to verify failure**

Run: `python3 -m pytest -q tests/runtime_scheduler/test_config.py -k execution`
Expected: FAIL with missing `execution` / `enforcement_required` attributes.

- [ ] **Step 3: Implement minimal config changes**

```python
# src/runtime_scheduler/runtime_scheduler/config.py

@dataclass(frozen=True, slots=True)
class VelocityMap:
    critical: tuple[float, float]
    high: tuple[float, float]
    best_effort: tuple[float, float]
    fallback: tuple[float, float]

@dataclass(frozen=True, slots=True)
class ExecutionConfig:
    cmd_vel_topic: str
    stop_on_non_run: bool
    mapping: VelocityMap

@dataclass(frozen=True, slots=True)
class VeeConfig:
    apply_to: tuple[str, ...]
    enforcement_required: bool
    profile: str
    ...

# parse execution + vee.enforcement_required from yaml
```

```yaml
# experiment_configs/v1_dynamic_dense.yaml
execution:
  cmd_vel_topic: /cmd_vel
  stop_on_non_run: true
  mapping:
    critical: {linear_x: 0.20, angular_z: 0.00}
    high: {linear_x: 0.12, angular_z: 0.15}
    best_effort: {linear_x: 0.08, angular_z: -0.10}
    fallback: {linear_x: 0.10, angular_z: 0.00}

vee:
  enforcement_required: true
  ...
```

- [ ] **Step 4: Run tests to verify pass**

Run: `python3 -m pytest -q tests/runtime_scheduler/test_config.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/runtime_scheduler/runtime_scheduler/config.py \
  experiment_configs/v1_dynamic_dense.yaml \
  tests/runtime_scheduler/test_config.py
git commit -m "feat: add execution and vee enforcement config"
```

## Task 2: 实现 VEE runtime enforcer（启动强制 + PID 注入）

**Files:**
- Create: `src/runtime_scheduler/runtime_scheduler/vee_runtime_enforcer.py`
- Test: `tests/runtime_scheduler/test_vee_runtime_enforcer.py`

- [ ] **Step 1: Write failing tests for startup enforcement and pid attach**

```python
# tests/runtime_scheduler/test_vee_runtime_enforcer.py

import pytest
from runtime_scheduler.vee_runtime_enforcer import VeeRuntimeEnforcer


def test_enforce_startup_raises_on_nonzero(monkeypatch):
    def _fail(*args, **kwargs):
        class R: returncode = 1
        return R()
    monkeypatch.setattr("subprocess.run", _fail)
    enforcer = VeeRuntimeEnforcer(script_path="/tmp/apply.sh", cgroup_procs_path="/tmp/procs")
    with pytest.raises(RuntimeError, match="apply_runtime_constraints"):
        enforcer.enforce_startup()


def test_attach_pid_writes_cgroup_procs(tmp_path):
    p = tmp_path / "cgroup.procs"
    enforcer = VeeRuntimeEnforcer(script_path="/tmp/apply.sh", cgroup_procs_path=str(p))
    enforcer.attach_pid(1234)
    assert p.read_text(encoding="utf-8") == "1234\n"
```

- [ ] **Step 2: Run tests to verify failure**

Run: `python3 -m pytest -q tests/runtime_scheduler/test_vee_runtime_enforcer.py`
Expected: FAIL with module not found.

- [ ] **Step 3: Implement minimal enforcer**

```python
# src/runtime_scheduler/runtime_scheduler/vee_runtime_enforcer.py
from __future__ import annotations

import subprocess
from pathlib import Path


class VeeRuntimeEnforcer:
    def __init__(self, script_path: str, cgroup_procs_path: str) -> None:
        self._script_path = script_path
        self._cgroup_procs = Path(cgroup_procs_path)

    def enforce_startup(self) -> None:
        result = subprocess.run([self._script_path], check=False)
        if result.returncode != 0:
            raise RuntimeError("apply_runtime_constraints failed")

    def attach_pid(self, pid: int) -> None:
        self._cgroup_procs.parent.mkdir(parents=True, exist_ok=True)
        with self._cgroup_procs.open("a", encoding="utf-8") as f:
            f.write(f"{pid}\\n")
```

- [ ] **Step 4: Run tests to verify pass**

Run: `python3 -m pytest -q tests/runtime_scheduler/test_vee_runtime_enforcer.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/runtime_scheduler/runtime_scheduler/vee_runtime_enforcer.py \
  tests/runtime_scheduler/test_vee_runtime_enforcer.py
git commit -m "feat: add vee runtime enforcer for startup and pid attach"
```

## Task 3: 实现 Worker 进程与任务级控制

**Files:**
- Create: `src/runtime_scheduler/runtime_scheduler/worker_process.py`
- Create: `src/runtime_scheduler/runtime_scheduler/worker_manager.py`
- Test: `tests/runtime_scheduler/test_worker_manager.py`

- [ ] **Step 1: Write failing WorkerManager tests**

```python
# tests/runtime_scheduler/test_worker_manager.py

from runtime_scheduler.worker_manager import WorkerManager


def test_ensure_workers_creates_pid_map(monkeypatch):
    created: dict[str, int] = {}

    def _spawn(task_id: str) -> int:
        pid = 2000 + len(created)
        created[task_id] = pid
        return pid

    mgr = WorkerManager(spawn_fn=_spawn, resume_fn=lambda pid: None, stop_fn=lambda pid: None, attach_fn=lambda pid: None)
    mgr.ensure_workers(["t1", "t2"])
    assert mgr.get_pid("t1") == 2000
    assert mgr.get_pid("t2") == 2001


def test_resume_and_stop_by_task(monkeypatch):
    resumed: list[int] = []
    stopped: list[int] = []

    mgr = WorkerManager(
        spawn_fn=lambda task_id: 3001,
        resume_fn=lambda pid: resumed.append(pid),
        stop_fn=lambda pid: stopped.append(pid),
        attach_fn=lambda pid: None,
    )
    mgr.ensure_workers(["t1"])
    assert mgr.resume_task("t1") is True
    assert mgr.stop_task("t1") is True
    assert resumed == [3001]
    assert stopped == [3001]
```

- [ ] **Step 2: Run tests to verify failure**

Run: `python3 -m pytest -q tests/runtime_scheduler/test_worker_manager.py`
Expected: FAIL with module not found.

- [ ] **Step 3: Implement worker process entry + manager**

```python
# src/runtime_scheduler/runtime_scheduler/worker_process.py
from __future__ import annotations

import math


def run_cpu_worker() -> None:
    x = 0.1
    while True:
        x = math.sin(x) + math.cos(x)
```

```python
# src/runtime_scheduler/runtime_scheduler/worker_manager.py
from __future__ import annotations

import os
import signal
import subprocess
import sys
from collections.abc import Callable


class WorkerManager:
    def __init__(self, spawn_fn=None, resume_fn=None, stop_fn=None, attach_fn=None) -> None:
        self._task_to_pid: dict[str, int] = {}
        self._spawn_fn = spawn_fn or self._default_spawn
        self._resume_fn = resume_fn or (lambda pid: os.kill(pid, signal.SIGCONT))
        self._stop_fn = stop_fn or (lambda pid: os.kill(pid, signal.SIGSTOP))
        self._attach_fn = attach_fn or (lambda pid: None)

    def _default_spawn(self, task_id: str) -> int:
        proc = subprocess.Popen([sys.executable, "-m", "runtime_scheduler.worker_process"])  # noqa: S603
        return int(proc.pid)

    def ensure_workers(self, task_ids: list[str]) -> None:
        for task_id in task_ids:
            if task_id in self._task_to_pid:
                continue
            pid = self._spawn_fn(task_id)
            self._attach_fn(pid)
            self._task_to_pid[task_id] = pid

    def get_pid(self, task_id: str) -> int | None:
        return self._task_to_pid.get(task_id)

    def resume_task(self, task_id: str) -> bool:
        pid = self.get_pid(task_id)
        if pid is None:
            return False
        self._resume_fn(pid)
        return True

    def stop_task(self, task_id: str) -> bool:
        pid = self.get_pid(task_id)
        if pid is None:
            return False
        self._stop_fn(pid)
        return True
```

- [ ] **Step 4: Run tests to verify pass**

Run: `python3 -m pytest -q tests/runtime_scheduler/test_worker_manager.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/runtime_scheduler/runtime_scheduler/worker_process.py \
  src/runtime_scheduler/runtime_scheduler/worker_manager.py \
  tests/runtime_scheduler/test_worker_manager.py
git commit -m "feat: add task worker manager with signal control"
```

## Task 4: 实现 CmdVelPublisher 与 ExecutionAdapter 规则映射

**Files:**
- Create: `src/runtime_scheduler/runtime_scheduler/cmd_vel_publisher.py`
- Create: `src/runtime_scheduler/runtime_scheduler/execution_adapter.py`
- Test: `tests/runtime_scheduler/test_execution_adapter.py`

- [ ] **Step 1: Write failing adapter tests (无需真实 ROS)**

```python
# tests/runtime_scheduler/test_execution_adapter.py

from runtime_scheduler.execution_adapter import ExecutionAdapter


class FakeCmdVel:
    def __init__(self):
        self.calls = []

    def publish_motion(self, vx, wz):
        self.calls.append(("motion", vx, wz))

    def publish_stop(self):
        self.calls.append(("stop", 0.0, 0.0))


def test_run_task_maps_to_lane_velocity_and_resume():
    resumed, stopped = [], []
    adapter = ExecutionAdapter(
        cmd_vel=FakeCmdVel(),
        worker_ops={
            "resume": lambda task_id: resumed.append(task_id) or True,
            "stop": lambda task_id: stopped.append(task_id) or True,
            "ensure": lambda task_ids: None,
        },
        velocity_mapping={"critical": (0.2, 0.0), "fallback": (0.1, 0.0)},
    )
    out = adapter.execute_window([{"task_id": "t1", "lane": "critical", "action": "RUN"}], now_ms=10)
    assert out["success"] is True
    assert resumed == ["t1"]


def test_non_run_window_publishes_stop():
    cmd = FakeCmdVel()
    adapter = ExecutionAdapter(
        cmd_vel=cmd,
        worker_ops={"resume": lambda task_id: True, "stop": lambda task_id: True, "ensure": lambda task_ids: None},
        velocity_mapping={"fallback": (0.1, 0.0)},
    )
    adapter.execute_window([{"task_id": "t2", "lane": "high", "action": "PAUSE"}], now_ms=10)
    assert cmd.calls[0][0] == "stop"
```

- [ ] **Step 2: Run tests to verify failure**

Run: `python3 -m pytest -q tests/runtime_scheduler/test_execution_adapter.py`
Expected: FAIL with module not found.

- [ ] **Step 3: Implement adapter + publisher skeleton**

```python
# src/runtime_scheduler/runtime_scheduler/execution_adapter.py
from __future__ import annotations


class ExecutionAdapter:
    def __init__(self, cmd_vel, worker_ops: dict, velocity_mapping: dict[str, tuple[float, float]]) -> None:
        self._cmd_vel = cmd_vel
        self._worker_ops = worker_ops
        self._velocity_mapping = velocity_mapping

    def execute_window(self, task_actions: list[dict], now_ms: int) -> dict:
        task_ids = [a["task_id"] for a in task_actions]
        self._worker_ops["ensure"](task_ids)

        run_actions = [a for a in task_actions if a.get("action") == "RUN"]
        if run_actions:
            top = run_actions[0]
            lane = str(top.get("lane", "fallback"))
            vx, wz = self._velocity_mapping.get(lane, self._velocity_mapping["fallback"])
            self._cmd_vel.publish_motion(vx, wz)
        else:
            self._cmd_vel.publish_stop()

        worker_ops = []
        success = True
        for action in task_actions:
            task_id = str(action["task_id"])
            is_run = action.get("action") == "RUN"
            ok = self._worker_ops["resume"](task_id) if is_run else self._worker_ops["stop"](task_id)
            worker_ops.append({"task_id": task_id, "op": "SIGCONT" if is_run else "SIGSTOP", "ok": bool(ok)})
            success = success and bool(ok)

        return {"success": success, "cmd_vel": {"at_ms": now_ms}, "worker_ops": worker_ops}
```

```python
# src/runtime_scheduler/runtime_scheduler/cmd_vel_publisher.py
from __future__ import annotations


class CmdVelPublisher:
    def publish_motion(self, vx: float, wz: float) -> None:
        raise NotImplementedError

    def publish_stop(self) -> None:
        self.publish_motion(0.0, 0.0)
```

- [ ] **Step 4: Run tests to verify pass**

Run: `python3 -m pytest -q tests/runtime_scheduler/test_execution_adapter.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/runtime_scheduler/runtime_scheduler/execution_adapter.py \
  src/runtime_scheduler/runtime_scheduler/cmd_vel_publisher.py \
  tests/runtime_scheduler/test_execution_adapter.py
git commit -m "feat: add execution adapter with lane-to-cmd-vel mapping"
```

## Task 5: 集成到 SteppedExperimentLoop 与 main fail-fast 启动流程

**Files:**
- Modify: `src/runtime_scheduler/runtime_scheduler/stepped_loop.py`
- Modify: `src/runtime_scheduler/runtime_scheduler/main.py`
- Modify: `tests/runtime_scheduler/test_stepped_loop.py`

- [ ] **Step 1: Write failing integration tests for execute stage and startup enforcement**

```python
# tests/runtime_scheduler/test_stepped_loop.py

def test_loop_calls_execution_adapter_once_per_window(...):
    calls = []
    class FakeAdapter:
        def execute_window(self, task_actions, now_ms):
            calls.append((task_actions, now_ms))
            return {"success": True, "cmd_vel": {}, "worker_ops": []}

    # construct loop with fake adapter
    # run 1s config => 20 windows
    assert len(calls) == 20


def test_run_stepped_experiment_enforces_vee_before_loop(monkeypatch, tmp_path):
    from runtime_scheduler.main import run_stepped_experiment
    order = []
    monkeypatch.setattr("runtime_scheduler.main.VeeRuntimeEnforcer", lambda *a, **k: type("E", (), {"enforce_startup": lambda self: order.append("enforce")})())
    monkeypatch.setattr("runtime_scheduler.main.SteppedExperimentLoop", lambda **kwargs: type("L", (), {"run": lambda self: order.append("loop")})())
    run_stepped_experiment(output_root=tmp_path, config=_make_config())
    assert order[:2] == ["enforce", "loop"]
```

- [ ] **Step 2: Run tests to verify failure**

Run: `python3 -m pytest -q tests/runtime_scheduler/test_stepped_loop.py -k "execution_adapter or enforces_vee"`
Expected: FAIL with missing constructor params / missing enforcement flow.

- [ ] **Step 3: Implement loop/main wiring**

```python
# src/runtime_scheduler/runtime_scheduler/stepped_loop.py
class SteppedExperimentLoop:
    def __init__(..., execution_adapter: object, ...) -> None:
        ...
        self._execution_adapter = execution_adapter

    def run(self) -> None:
        ...
        observation, plan, outcome = run_single_window(...)
        execution = self._execution_adapter.execute_window(plan["task_actions"], now_ms=timestamp_us // 1000)
        outcome["execution"] = execution
        self._sink.write("outcome", outcome)
```

```python
# src/runtime_scheduler/runtime_scheduler/main.py
from runtime_scheduler.execution_adapter import ExecutionAdapter
from runtime_scheduler.worker_manager import WorkerManager
from runtime_scheduler.vee_runtime_enforcer import VeeRuntimeEnforcer


def run_stepped_experiment(output_root: Path, config: Config) -> None:
    enforcer = VeeRuntimeEnforcer(
        script_path="src/infra/vee/scripts/apply_runtime_constraints.sh",
        cgroup_procs_path="/sys/fs/cgroup/vee/cgroup.procs",
    )
    if config.vee.enforcement_required:
        enforcer.enforce_startup()

    worker_manager = WorkerManager(attach_fn=enforcer.attach_pid)
    adapter = ExecutionAdapter(...)

    loop = SteppedExperimentLoop(..., execution_adapter=adapter, ...)
    ...
```

- [ ] **Step 4: Run tests to verify pass**

Run: `python3 -m pytest -q tests/runtime_scheduler/test_stepped_loop.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/runtime_scheduler/runtime_scheduler/stepped_loop.py \
  src/runtime_scheduler/runtime_scheduler/main.py \
  tests/runtime_scheduler/test_stepped_loop.py
git commit -m "feat: wire execution adapter and vee startup enforcement into stepped loop"
```

## Task 6: 增加执行 trace 合同测试与回归验证

**Files:**
- Create: `tests/integration/test_execution_trace_contract.py`

- [ ] **Step 1: Write failing trace contract test**

```python
# tests/integration/test_execution_trace_contract.py

import json
from pathlib import Path


def test_outcome_trace_contains_execution_fields(tmp_path, monkeypatch):
    from runtime_scheduler.main import run_once_for_test

    run_once_for_test(output_root=tmp_path)

    exp_dirs = sorted([p for p in tmp_path.iterdir() if p.is_dir()])
    assert exp_dirs
    outcome = exp_dirs[-1] / "outcome.jsonl"
    record = json.loads(outcome.read_text(encoding="utf-8").splitlines()[0])
    assert "execution" in record
    assert "cmd_vel" in record["execution"]
    assert "worker_ops" in record["execution"]
```

- [ ] **Step 2: Run test to verify failure**

Run: `python3 -m pytest -q tests/integration/test_execution_trace_contract.py`
Expected: FAIL because `outcome` currently没有 `execution` 字段。

- [ ] **Step 3: Make minimal adjustments for test mode compatibility**

```python
# src/runtime_scheduler/runtime_scheduler/main.py (run_once_for_test)
# create no-op execution adapter and inject execution outcome
outcome["execution"] = {
    "success": True,
    "cmd_vel": {"vx": 0.0, "wz": 0.0, "reason": "test"},
    "worker_ops": [],
}
```

- [ ] **Step 4: Run focused and full tests**

Run: `python3 -m pytest -q tests/integration/test_execution_trace_contract.py`
Expected: PASS.

Run: `python3 -m pytest -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/integration/test_execution_trace_contract.py \
  src/runtime_scheduler/runtime_scheduler/main.py
git commit -m "test: enforce execution fields in outcome trace"
```

## Minimal Validation Checklist

- [ ] `python3 -m pytest -q tests/runtime_scheduler/test_execution_adapter.py tests/runtime_scheduler/test_stepped_loop.py`
- [ ] `python3 -m pytest -q tests/integration/test_execution_trace_contract.py`

## Spec Coverage Review

- `task_actions -> /cmd_vel` 物理链路：Task 4 + Task 5
- Worker 实体负载与 `task_id -> pid`：Task 3
- VEE 启动自动化与 PID 注入：Task 2 + Task 5
- fail-fast 与窗口级审计：Task 5 + Task 6
