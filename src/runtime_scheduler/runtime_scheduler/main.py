from __future__ import annotations

import time
import warnings
from pathlib import Path

from runtime_scheduler.cmd_vel_publisher import CmdVelPublisher
from runtime_scheduler.config import Config, load_config
from runtime_scheduler.execution_adapter import ExecutionAdapter
from runtime_scheduler.experiment_id import make_experiment_id
from runtime_scheduler.runtime_loop import run_single_window
from runtime_scheduler.stepped_loop import SteppedExperimentLoop
from runtime_scheduler.vee_runtime_enforcer import VeeRuntimeEnforcer
from runtime_scheduler.worker_manager import WorkerManager
from runtime_scheduler.workload_generator import PoissonLocalToolGenerator
from telemetry.real_resource_sampler import RealResourceSampler
from telemetry.resource_sampler import make_resource_sample
from telemetry.trace_sink import TraceSink

CONFIG_PATH = Path("experiment_configs/v1_dynamic_dense.yaml")
WINDOW_ID = "window-1"
WINDOW_TIMESTAMP_US = 1_000_000


def _task_event_from_arrival(experiment_id: str, arrival: dict[str, object]) -> dict[str, object]:
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


def run_once_for_test(output_root: Path, config: Config | None = None) -> None:
    runtime_config = config or load_config(CONFIG_PATH)
    experiment_id = make_experiment_id()
    sink = TraceSink(root_dir=output_root, experiment_id=experiment_id)
    generator = PoissonLocalToolGenerator(
        lambda_per_sec=runtime_config.agent_workload.local_tool.lambda_per_sec,
        window_ms=runtime_config.scheduler.window_ms,
        seed=runtime_config.agent_workload.seed,
        max_arrivals_per_window=runtime_config.agent_workload.local_tool.max_arrivals_per_window,
    )

    timestamp_us = WINDOW_TIMESTAMP_US
    arrivals = generator.next_arrivals(window_id=WINDOW_ID, timestamp_us=timestamp_us)
    if not arrivals:
        arrivals = [
            {
                "event_type": "TASK_ARRIVAL",
                "task_id": "local-tool-1",
                "request_id": "request-1",
                "window_id": WINDOW_ID,
                "timestamp_us": timestamp_us,
                "arrival_source": "poisson",
                "generator_seed": runtime_config.agent_workload.seed,
                "lambda_per_sec": runtime_config.agent_workload.local_tool.lambda_per_sec,
            }
        ]

    tasks = [{"task_id": arrival["task_id"], "priority_class": "ELASTIC"} for arrival in arrivals]

    for arrival in arrivals:
        sink.write("task_events", _task_event_from_arrival(experiment_id, arrival))

    observation, plan, outcome = run_single_window(window_id=WINDOW_ID, timestamp_us=timestamp_us, tasks=tasks)
    outcome["execution"] = {
        "cmd_vel": {"linear_x": 0.0, "angular_z": 0.0},
        "worker_ops": [],
    }
    sink.write("window_observation", observation)
    sink.write("plan", plan)
    sink.write("outcome", outcome)

    sink.write(
        "resource_samples",
        make_resource_sample(
            experiment_id=experiment_id,
            sample_id="sample-1",
            timestamp_us=int(time.time() * 1_000_000),
        ),
    )


def run_experiment(output_root: Path, config: Config) -> None:
    experiment_id = make_experiment_id()
    sink = TraceSink(root_dir=output_root, experiment_id=experiment_id)
    generator = PoissonLocalToolGenerator(
        lambda_per_sec=config.agent_workload.local_tool.lambda_per_sec,
        window_ms=config.scheduler.window_ms,
        seed=config.agent_workload.seed,
        max_arrivals_per_window=config.agent_workload.local_tool.max_arrivals_per_window,
    )

    total_windows = max(1, int((config.experiment.duration_sec * 1000) / config.scheduler.window_ms))
    base_timestamp_us = int(time.time() * 1_000_000)
    window_step_us = config.scheduler.window_ms * 1_000

    for idx in range(total_windows):
        window_id = f"window-{idx + 1}"
        timestamp_us = base_timestamp_us + (idx * window_step_us)
        arrivals = generator.next_arrivals(window_id=window_id, timestamp_us=timestamp_us)

        # Ensure task_events file always exists for baseline trace completeness.
        if idx == 0 and not arrivals:
            arrivals = [
                {
                    "event_type": "TASK_ARRIVAL",
                    "task_id": "local-tool-1",
                    "request_id": "request-1",
                    "window_id": window_id,
                    "timestamp_us": timestamp_us,
                    "arrival_source": "poisson",
                    "generator_seed": config.agent_workload.seed,
                    "lambda_per_sec": config.agent_workload.local_tool.lambda_per_sec,
                }
            ]

        tasks = [{"task_id": arrival["task_id"], "priority_class": "ELASTIC"} for arrival in arrivals]
        for arrival in arrivals:
            sink.write("task_events", _task_event_from_arrival(experiment_id, arrival))

        observation, plan, outcome = run_single_window(
            window_id=window_id,
            timestamp_us=timestamp_us,
            tasks=tasks,
        )
        sink.write("window_observation", observation)
        sink.write("plan", plan)
        sink.write("outcome", outcome)
        sink.write(
            "resource_samples",
            make_resource_sample(
                experiment_id=experiment_id,
                sample_id=f"sample-{idx + 1}",
                timestamp_us=timestamp_us,
            ),
        )


def run_stepped_experiment(output_root: Path, config: Config) -> None:
    from gazebo.sim_stepper import SimStepper

    experiment_id = make_experiment_id()
    sink = TraceSink(root_dir=output_root, experiment_id=experiment_id)
    enforcer = VeeRuntimeEnforcer(
        script_path="src/infra/vee/scripts/apply_runtime_constraints.sh",
        cgroup_procs_path="/sys/fs/cgroup/vee/cgroup.procs",
    )
    if config.vee.enforcement_required:
        enforcer.enforce_startup()

    worker_manager = WorkerManager(attach_fn=enforcer.attach_pid)
    velocity_mapping = {
        "critical": (
            config.execution.mapping.critical.linear_x,
            config.execution.mapping.critical.angular_z,
        ),
        "high": (
            config.execution.mapping.high.linear_x,
            config.execution.mapping.high.angular_z,
        ),
        "best_effort": (
            config.execution.mapping.best_effort.linear_x,
            config.execution.mapping.best_effort.angular_z,
        ),
        "fallback": (
            config.execution.mapping.fallback.linear_x,
            config.execution.mapping.fallback.angular_z,
        ),
    }
    cmd_vel_publisher = CmdVelPublisher(topic=config.execution.cmd_vel_topic)
    execution_adapter = ExecutionAdapter(
        cmd_vel_publisher=cmd_vel_publisher,
        ensure=worker_manager.ensure_workers,
        resume=worker_manager.resume_task,
        stop=worker_manager.stop_task,
        velocity_mapping=velocity_mapping,
    )
    generator = PoissonLocalToolGenerator(
        lambda_per_sec=config.agent_workload.local_tool.lambda_per_sec,
        window_ms=config.scheduler.window_ms,
        seed=config.agent_workload.seed,
        max_arrivals_per_window=config.agent_workload.local_tool.max_arrivals_per_window,
    )

    stepper = SimStepper(config.sim.world_name, config.sim.physics_step_ms)
    sampler = RealResourceSampler(sample_interval_ms=config.scheduler.window_ms)
    loop = SteppedExperimentLoop(
        stepper=stepper,
        sampler=sampler,
        generator=generator,
        sink=sink,
        config=config,
        experiment_id=experiment_id,
        execution_adapter=execution_adapter,
    )
    try:
        loop.run()
    finally:
        stepper.close()
        cmd_vel_publisher.close()


def main() -> None:
    config = load_config(CONFIG_PATH)
    try:
        run_stepped_experiment(output_root=config.trace.root_dir, config=config)
    except ImportError:
        warnings.warn(
            "gz-transport Python bindings not found; falling back to wall-clock run_experiment(). "
            "Install gz-transport to enable step-locked simulation.",
            RuntimeWarning,
            stacklevel=1,
        )
        run_experiment(output_root=config.trace.root_dir, config=config)


if __name__ == "__main__":
    main()
