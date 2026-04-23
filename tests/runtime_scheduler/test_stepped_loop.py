from __future__ import annotations

import types
import json
from pathlib import Path

from runtime_scheduler.config import (
    AgentConfig,
    AgentWorkloadConfig,
    Config,
    ExecutionConfig,
    ExecutionMappingConfig,
    ExperimentConfig,
    LocalToolArrivalConfig,
    ScenarioConfig,
    SchedulerConfig,
    SimConfig,
    TraceConfig,
    TriggerConfig,
    VelocityConfig,
    VeeConfig,
    VeeCpuConfig,
    VeeGpuConfig,
    VeeMemoryConfig,
)
from runtime_scheduler.stepped_loop import SteppedExperimentLoop
from runtime_scheduler.task_catalog import CONTROLLER_TASK_IDS
from runtime_scheduler.workload_generator import PoissonLocalToolGenerator
from telemetry.trace_sink import TraceSink


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
        execution=ExecutionConfig(
            cmd_vel_topic="/cmd_vel",
            stop_on_non_run=True,
            mapping=ExecutionMappingConfig(
                critical=VelocityConfig(linear_x=0.6, angular_z=0.2),
                high=VelocityConfig(linear_x=0.4, angular_z=0.1),
                best_effort=VelocityConfig(linear_x=0.2, angular_z=0.05),
                fallback=VelocityConfig(linear_x=0.0, angular_z=0.0),
            ),
        ),
        sim=SimConfig(world_name="test_world", physics_step_ms=1),
        vee=VeeConfig(
            apply_to=("workers",),
            enforcement_required=False,
            profile="test",
            cpu=VeeCpuConfig(cpuset="0", quota="100000 1000000"),
            memory=VeeMemoryConfig(high="1G", max="2G"),
            gpu=VeeGpuConfig(provider="none"),
        ),
        trace=TraceConfig(root_dir=Path("traces")),
    )


class MockStepper:
    def __init__(self, window_ms: int) -> None:
        self._step_us = window_ms * 1_000
        self._current_us = 0
        self.step_calls = 0

    def sim_time_us(self) -> int:
        return self._current_us

    def step(self, n_steps: int) -> None:
        self._current_us += n_steps * 1_000
        self.step_calls += 1


class MockSampler:
    def sample(self) -> dict[str, object]:
        return {
            "schema_version": "v1",
            "scope": "system",
            "cpu": {"utilization_total": 0.0},
            "memory": {"used_bytes": 0, "available_bytes": 0},
            "gpu": {"utilization": 0.0, "memory_used_bytes": 0},
            "network": {"tx_rate_bps": 0, "rx_rate_bps": 0},
        }


class RecordingExecutionAdapter:
    def __init__(self, payload: dict[str, object] | None = None) -> None:
        self.calls: list[tuple[list[dict[str, object]], int]] = []
        self.payload = payload or {
            "success": True,
            "cmd_vel": {"type": "stop", "vx": 0.0, "wz": 0.0},
            "worker_ops": [],
        }

    def execute_window(self, task_actions: list[dict[str, object]], now_ms: int) -> dict[str, object]:
        self.calls.append((task_actions, now_ms))
        return dict(self.payload)


def test_loop_injects_controller_tasks_into_plan_and_task_events(tmp_path):
    config = _make_config(duration_sec=1)
    stepper = MockStepper(window_ms=50)
    sampler = MockSampler()
    sink = TraceSink(root_dir=tmp_path, experiment_id="test-exp-controller")
    generator = PoissonLocalToolGenerator(
        lambda_per_sec=0.0, window_ms=50, seed=0, max_arrivals_per_window=0
    )
    execution_adapter = RecordingExecutionAdapter()

    loop = SteppedExperimentLoop(
        stepper,
        sampler,
        generator,
        sink,
        config,
        "test-exp-controller",
        execution_adapter,
    )
    loop.run()

    plan_file = tmp_path / "test-exp-controller" / "plan.jsonl"
    first_plan = json.loads(plan_file.read_text(encoding="utf-8").splitlines()[0])
    task_actions = {action["task_id"]: action for action in first_plan["task_actions"]}
    for task_id in CONTROLLER_TASK_IDS:
        assert task_id in task_actions
        assert task_actions[task_id]["lane"] == "CRITICAL_LANE"

    task_events_file = tmp_path / "test-exp-controller" / "task_events.jsonl"
    task_events = [
        json.loads(line)
        for line in task_events_file.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    controller_events = [
        event
        for event in task_events
        if event["task_type"] == "ROS_CONTROLLER_CYCLE" and event["window_id"] == "window-1"
    ]
    assert len(controller_events) == len(CONTROLLER_TASK_IDS)
    for event in controller_events:
        assert event["source"] == "controller_runtime"
        assert event["event_type"] == "TASK_ARRIVAL"
        assert event["arrival_source"] == "periodic_controller"
        assert event["generator_seed"] == -1
        assert event["lambda_per_sec"] == 0.0


def test_loop_exits_after_correct_number_of_windows(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "runtime_scheduler.stepped_loop.run_single_window",
        lambda window_id, timestamp_us, tasks: (
            {
                "schema_version": "v1",
                "window_id": window_id,
                "timestamp_us": timestamp_us,
                "scheduler_version": "v1",
                "policy_hash": "critical_first_fifo",
            },
            {
                "schema_version": "v1",
                "plan_id": f"plan-{window_id}",
                "window_id": window_id,
                "generated_at_us": timestamp_us,
                "scheduler_version": "v1",
                "policy_hash": "critical_first_fifo",
                "task_actions": [],
            },
            {
                "schema_version": "v1",
                "outcome_id": f"outcome-{window_id}",
                "window_id": window_id,
                "plan_id": f"plan-{window_id}",
                "scheduler_version": "v1",
                "policy_hash": "critical_first_fifo",
            },
        ),
    )

    config = _make_config(duration_sec=1)
    stepper = MockStepper(window_ms=50)
    sampler = MockSampler()
    sink = TraceSink(root_dir=tmp_path, experiment_id="test-exp-1")
    generator = PoissonLocalToolGenerator(
        lambda_per_sec=0.0, window_ms=50, seed=0, max_arrivals_per_window=0
    )
    execution_adapter = RecordingExecutionAdapter()

    loop = SteppedExperimentLoop(
        stepper,
        sampler,
        generator,
        sink,
        config,
        "test-exp-1",
        execution_adapter,
    )
    loop.run()

    assert stepper.step_calls == 20


def test_loop_writes_one_resource_sample_per_window(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "runtime_scheduler.stepped_loop.run_single_window",
        lambda window_id, timestamp_us, tasks: (
            {
                "schema_version": "v1",
                "window_id": window_id,
                "timestamp_us": timestamp_us,
                "scheduler_version": "v1",
                "policy_hash": "critical_first_fifo",
            },
            {
                "schema_version": "v1",
                "plan_id": f"plan-{window_id}",
                "window_id": window_id,
                "generated_at_us": timestamp_us,
                "scheduler_version": "v1",
                "policy_hash": "critical_first_fifo",
                "task_actions": [],
            },
            {
                "schema_version": "v1",
                "outcome_id": f"outcome-{window_id}",
                "window_id": window_id,
                "plan_id": f"plan-{window_id}",
                "scheduler_version": "v1",
                "policy_hash": "critical_first_fifo",
            },
        ),
    )

    config = _make_config(duration_sec=1)
    stepper = MockStepper(window_ms=50)
    sampler = MockSampler()
    sink = TraceSink(root_dir=tmp_path, experiment_id="test-exp-2")
    generator = PoissonLocalToolGenerator(
        lambda_per_sec=0.0, window_ms=50, seed=0, max_arrivals_per_window=0
    )
    execution_payload = {
        "success": True,
        "mode": "stepped_online",
        "cmd_vel": {"type": "motion", "vx": 0.4, "wz": 0.1},
        "worker_ops": [{"task_id": "local-tool-1", "op": "resume", "ok": True}],
    }
    execution_adapter = RecordingExecutionAdapter(payload=execution_payload)

    loop = SteppedExperimentLoop(
        stepper,
        sampler,
        generator,
        sink,
        config,
        "test-exp-2",
        execution_adapter,
    )
    loop.run()

    resource_file = tmp_path / "test-exp-2" / "resource_samples.jsonl"
    lines = [l for l in resource_file.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(lines) == 20
    assert len(execution_adapter.calls) == 20

    outcome_file = tmp_path / "test-exp-2" / "outcome.jsonl"
    outcome_lines = [l for l in outcome_file.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(outcome_lines) == 20
    first_outcome = json.loads(outcome_lines[0])
    assert first_outcome["execution"] == execution_payload

    controller_cycle_file = tmp_path / "test-exp-2" / "controller_cycle_samples.jsonl"
    controller_cycle_lines = [l for l in controller_cycle_file.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(controller_cycle_lines) == 40


def test_run_stepped_experiment_wires_and_closes_stepper(tmp_path, monkeypatch):
    from runtime_scheduler.main import run_stepped_experiment

    cfg = _make_config(duration_sec=1)
    cfg = Config(
        experiment=cfg.experiment,
        scenario=cfg.scenario,
        scheduler=cfg.scheduler,
        trigger=cfg.trigger,
        agent=cfg.agent,
        agent_workload=cfg.agent_workload,
        execution=cfg.execution,
        sim=cfg.sim,
        vee=VeeConfig(
            apply_to=cfg.vee.apply_to,
            enforcement_required=True,
            profile=cfg.vee.profile,
            cpu=cfg.vee.cpu,
            memory=cfg.vee.memory,
            gpu=cfg.vee.gpu,
        ),
        trace=TraceConfig(root_dir=tmp_path),
    )

    class FakeStepper:
        def __init__(self, world_name: str, physics_step_ms: int):
            self.world_name = world_name
            self.physics_step_ms = physics_step_ms
            self.closed = False

        def sim_time_us(self) -> int:
            return 1_000_000

        def step(self, n_steps: int) -> None:
            return None

        def close(self) -> None:
            self.closed = True

    fake_stepper = FakeStepper(cfg.sim.world_name, cfg.sim.physics_step_ms)
    fake_module = types.SimpleNamespace(SimStepper=lambda world_name, physics_step_ms: fake_stepper)
    monkeypatch.setitem(__import__("sys").modules, "gazebo.sim_stepper", fake_module)
    events: list[str] = []

    class FakeEnforcer:
        def __init__(self, script_path: str, cgroup_procs_path: str):
            assert script_path == "src/infra/vee/scripts/apply_runtime_constraints.sh"
            assert cgroup_procs_path == "/sys/fs/cgroup/vee/cgroup.procs"
            events.append("enforcer_init")

        def enforce_startup(self) -> None:
            events.append("enforce_startup")

        def attach_pid(self, pid: int) -> None:
            events.append(f"attach_pid:{pid}")

    class FakeWorkerManager:
        def __init__(self, attach_fn):
            self.attach_fn = attach_fn
            events.append("worker_init")
            self.attach_fn(123)

        def ensure_workers(self, task_ids):
            del task_ids

        def resume_task(self, task_id):
            del task_id
            return True

        def stop_task(self, task_id):
            del task_id
            return True

    class FakeExecutionAdapter:
        def __init__(self, **kwargs):
            del kwargs
            events.append("execution_adapter_init")

    class FakeCmdVelPublisher:
        def __init__(self, topic: str):
            assert topic == cfg.execution.cmd_vel_topic
            events.append("cmd_vel_init")

        def publish_motion(self, vx: float, wz: float) -> None:
            del vx, wz

        def publish_stop(self) -> None:
            return None

        def close(self) -> None:
            events.append("cmd_vel_close")

    class FakeLoop:
        def __init__(self, **kwargs):
            del kwargs
            events.append("loop_init")

        def run(self):
            events.append("loop_run")

    monkeypatch.setattr("runtime_scheduler.main.VeeRuntimeEnforcer", FakeEnforcer)
    monkeypatch.setattr("runtime_scheduler.main.WorkerManager", FakeWorkerManager)
    monkeypatch.setattr("runtime_scheduler.main.CmdVelPublisher", FakeCmdVelPublisher)
    monkeypatch.setattr("runtime_scheduler.main.ExecutionAdapter", FakeExecutionAdapter)
    monkeypatch.setattr("runtime_scheduler.main.SteppedExperimentLoop", FakeLoop)

    run_stepped_experiment(output_root=tmp_path, config=cfg)
    assert fake_stepper.closed is True
    assert events.index("enforce_startup") < events.index("loop_run")
    assert "cmd_vel_close" in events


def test_main_falls_back_to_run_experiment_on_import_error(tmp_path, monkeypatch):
    from runtime_scheduler import main as main_module

    cfg = _make_config(duration_sec=1)
    cfg = Config(
        experiment=cfg.experiment,
        scenario=cfg.scenario,
        scheduler=cfg.scheduler,
        trigger=cfg.trigger,
        agent=cfg.agent,
        agent_workload=cfg.agent_workload,
        execution=cfg.execution,
        sim=cfg.sim,
        vee=cfg.vee,
        trace=TraceConfig(root_dir=tmp_path),
    )

    monkeypatch.setattr(main_module, "load_config", lambda _path: cfg)
    monkeypatch.setattr(
        main_module,
        "run_stepped_experiment",
        lambda output_root, config: (_ for _ in ()).throw(ImportError("missing gz")),
    )
    called: list[tuple[Path, Config]] = []
    monkeypatch.setattr(
        main_module,
        "run_experiment",
        lambda output_root, config: called.append((output_root, config)),
    )

    main_module.main()
    assert called == [(tmp_path, cfg)]
