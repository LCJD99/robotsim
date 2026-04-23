from __future__ import annotations

from runtime_scheduler.config import Config
from runtime_scheduler.controller_cycle_aggregator import (
    ControllerCycleAggregator,
    DEFAULT_CONTROLLER_NAMES,
    build_default_controller_cycle_records,
)
from runtime_scheduler.runtime_loop import run_single_window
from runtime_scheduler.task_catalog import (
    build_controller_periodic_tasks,
    build_controller_task_events,
    build_local_tool_task,
    build_local_tool_task_event,
)
from runtime_scheduler.workload_generator import PoissonLocalToolGenerator
from telemetry.trace_sink import TraceSink


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
        controller_cycle_source: object | None = None,
    ) -> None:
        self._stepper = stepper
        self._sampler = sampler
        self._generator = generator
        self._sink = sink
        self._config = config
        self._experiment_id = experiment_id
        self._execution_adapter = execution_adapter
        self._controller_cycle_source = controller_cycle_source
        self._period_target_us = int(self._config.scheduler.window_ms * 1_000)
        self._cycle_aggregator = ControllerCycleAggregator(
            controller_names=DEFAULT_CONTROLLER_NAMES,
            period_target_us=self._period_target_us,
        )

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
            tasks = [build_local_tool_task(arrival) for arrival in arrivals]
            tasks.extend(build_controller_periodic_tasks(window_id=window_id, timestamp_us=timestamp_us))
            for arrival in arrivals:
                self._sink.write("task_events", build_local_tool_task_event(self._experiment_id, arrival))
            for controller_event in build_controller_task_events(
                experiment_id=self._experiment_id,
                window_id=window_id,
                timestamp_us=timestamp_us,
            ):
                self._sink.write("task_events", controller_event)

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

            controller_cycle_records = self._get_controller_cycle_records(timestamp_us)
            for sample in self._cycle_aggregator.aggregate_window(
                experiment_id=self._experiment_id,
                window_id=window_id,
                timestamp_us=timestamp_us,
                records=controller_cycle_records,
            ):
                self._sink.write("controller_cycle_samples", sample)

            self._stepper.step(n_steps)
            window_idx += 1

    def _get_controller_cycle_records(self, timestamp_us: int) -> list[dict[str, object]]:
        if self._controller_cycle_source is None:
            return build_default_controller_cycle_records(
                window_start_us=timestamp_us,
                period_target_us=self._period_target_us,
            )

        source = self._controller_cycle_source
        if not hasattr(source, "drain_window"):
            raise ValueError("controller_cycle_source must provide drain_window(window_start_us, window_end_us)")

        window_end_us = timestamp_us + self._period_target_us
        records = source.drain_window(window_start_us=timestamp_us, window_end_us=window_end_us)
        return list(records)
