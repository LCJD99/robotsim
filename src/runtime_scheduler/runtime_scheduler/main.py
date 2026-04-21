from __future__ import annotations

import time
from pathlib import Path

from runtime_scheduler.config import Config, load_config
from runtime_scheduler.experiment_id import make_experiment_id
from runtime_scheduler.runtime_loop import run_single_window
from runtime_scheduler.workload_generator import PoissonLocalToolGenerator
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


def main() -> None:
    config = load_config(CONFIG_PATH)
    run_experiment(output_root=config.trace.root_dir, config=config)


if __name__ == "__main__":
    main()
