from __future__ import annotations

from runtime_scheduler.config import Config
from runtime_scheduler.runtime_loop import run_single_window
from runtime_scheduler.workload_generator import PoissonLocalToolGenerator
from telemetry.trace_sink import TraceSink


def _build_task_event(experiment_id: str, arrival: dict[str, object]) -> dict[str, object]:
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
    """Run scheduler windows against explicit Gazebo simulation steps."""

    def __init__(
        self,
        stepper: object,
        sampler: object,
        generator: PoissonLocalToolGenerator,
        sink: TraceSink,
        config: Config,
        experiment_id: str,
        execution_adapter: object,
    ) -> None:
        self._stepper = stepper
        self._sampler = sampler
        self._generator = generator
        self._sink = sink
        self._config = config
        self._experiment_id = experiment_id
        self._execution_adapter = execution_adapter

    def run(self) -> None:
        n_steps = self._config.scheduler.window_ms // self._config.sim.physics_step_ms
        if n_steps <= 0:
            raise ValueError("window_ms // physics_step_ms must be >= 1")
        duration_us = int(self._config.experiment.duration_sec * 1_000_000)

        window_idx = 0
        while self._stepper.sim_time_us() < duration_us:
            timestamp_us = self._stepper.sim_time_us()
            window_id = f"window-{window_idx + 1}"

            raw_sample = self._sampler.sample()
            resource_record: dict[str, object] = {
                **raw_sample,
                "experiment_id": self._experiment_id,
                "sample_id": f"sample-{window_idx + 1}",
                "timestamp_us": timestamp_us,
                "window_id": window_id,
            }

            arrivals = self._generator.next_arrivals(window_id, timestamp_us)
            tasks = [{"task_id": a["task_id"], "priority_class": "ELASTIC"} for a in arrivals]
            for arrival in arrivals:
                self._sink.write("task_events", _build_task_event(self._experiment_id, arrival))

            observation, plan, outcome = run_single_window(window_id, timestamp_us, tasks)
            execution = self._execution_adapter.execute_window(
                plan["task_actions"],
                now_ms=timestamp_us // 1000,
            )
            outcome = {**outcome, "execution": execution}
            self._sink.write("window_observation", observation)
            self._sink.write("plan", plan)
            self._sink.write("outcome", outcome)
            self._sink.write("resource_samples", resource_record)

            self._stepper.step(n_steps)
            window_idx += 1
