from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import yaml


@dataclass(frozen=True, slots=True)
class ExperimentConfig:
    duration_sec: int
    id_format: str


@dataclass(frozen=True, slots=True)
class ScenarioConfig:
    type: str


@dataclass(frozen=True, slots=True)
class SchedulerConfig:
    impl: str
    window_ms: int


@dataclass(frozen=True, slots=True)
class TriggerConfig:
    impl: str
    cooldown_windows: int


@dataclass(frozen=True, slots=True)
class AgentConfig:
    enabled_task_types: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class LocalToolArrivalConfig:
    lambda_per_sec: float
    max_arrivals_per_window: int


@dataclass(frozen=True, slots=True)
class AgentWorkloadConfig:
    generator: str
    seed: int
    local_tool: LocalToolArrivalConfig


@dataclass(frozen=True, slots=True)
class VeeCpuConfig:
    cpuset: str
    quota: str


@dataclass(frozen=True, slots=True)
class VeeMemoryConfig:
    high: str
    max: str


@dataclass(frozen=True, slots=True)
class VeeGpuConfig:
    provider: str


@dataclass(frozen=True, slots=True)
class VeeConfig:
    profile: str
    cpu: VeeCpuConfig
    memory: VeeMemoryConfig
    gpu: VeeGpuConfig


@dataclass(frozen=True, slots=True)
class TraceConfig:
    root_dir: Path


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


def _require_mapping(mapping: Mapping[str, Any], key: str, path: str) -> Mapping[str, Any]:
    value = _require_key(mapping, key, path)
    if not isinstance(value, Mapping):
        raise ValueError(f"expected mapping at {path}")
    return value


def _require_key(mapping: Mapping[str, Any], key: str, path: str) -> Any:
    if key not in mapping:
        raise ValueError(f"missing required key: {path}")
    return mapping[key]


def load_config(path: Path | str) -> Config:
    raw = yaml.safe_load(Path(path).read_text())
    if not isinstance(raw, Mapping):
        raise ValueError("config root must be a mapping")

    experiment = _require_mapping(raw, "experiment", "experiment")
    scenario = _require_mapping(raw, "scenario", "scenario")
    scheduler = _require_mapping(raw, "scheduler", "scheduler")
    trigger = _require_mapping(raw, "trigger", "trigger")
    agent = _require_mapping(raw, "agent", "agent")
    agent_workload = _require_mapping(raw, "agent_workload", "agent_workload")
    vee = _require_mapping(raw, "vee", "vee")
    trace = _require_mapping(raw, "trace", "trace")

    local_tool = _require_mapping(agent_workload, "local_tool", "agent_workload.local_tool")
    vee_cpu = _require_mapping(vee, "cpu", "vee.cpu")
    vee_memory = _require_mapping(vee, "memory", "vee.memory")
    vee_gpu = _require_mapping(vee, "gpu", "vee.gpu")

    enabled_task_types = _require_key(agent, "enabled_task_types", "agent.enabled_task_types")
    if not isinstance(enabled_task_types, list):
        raise ValueError("expected list at agent.enabled_task_types")

    return Config(
        experiment=ExperimentConfig(
            duration_sec=int(_require_key(experiment, "duration_sec", "experiment.duration_sec")),
            id_format=str(_require_key(experiment, "id_format", "experiment.id_format")),
        ),
        scenario=ScenarioConfig(
            type=str(_require_key(scenario, "type", "scenario.type")),
        ),
        scheduler=SchedulerConfig(
            impl=str(_require_key(scheduler, "impl", "scheduler.impl")),
            window_ms=int(_require_key(scheduler, "window_ms", "scheduler.window_ms")),
        ),
        trigger=TriggerConfig(
            impl=str(_require_key(trigger, "impl", "trigger.impl")),
            cooldown_windows=int(
                _require_key(trigger, "cooldown_windows", "trigger.cooldown_windows")
            ),
        ),
        agent=AgentConfig(enabled_task_types=tuple(str(value) for value in enabled_task_types)),
        agent_workload=AgentWorkloadConfig(
            generator=str(_require_key(agent_workload, "generator", "agent_workload.generator")),
            seed=int(_require_key(agent_workload, "seed", "agent_workload.seed")),
            local_tool=LocalToolArrivalConfig(
                lambda_per_sec=float(
                    _require_key(local_tool, "lambda_per_sec", "agent_workload.local_tool.lambda_per_sec")
                ),
                max_arrivals_per_window=int(
                    _require_key(
                        local_tool,
                        "max_arrivals_per_window",
                        "agent_workload.local_tool.max_arrivals_per_window",
                    )
                ),
            ),
        ),
        vee=VeeConfig(
            profile=str(_require_key(vee, "profile", "vee.profile")),
            cpu=VeeCpuConfig(
                cpuset=str(_require_key(vee_cpu, "cpuset", "vee.cpu.cpuset")),
                quota=str(_require_key(vee_cpu, "quota", "vee.cpu.quota")),
            ),
            memory=VeeMemoryConfig(
                high=str(_require_key(vee_memory, "high", "vee.memory.high")),
                max=str(_require_key(vee_memory, "max", "vee.memory.max")),
            ),
            gpu=VeeGpuConfig(
                provider=str(_require_key(vee_gpu, "provider", "vee.gpu.provider")),
            ),
        ),
        trace=TraceConfig(
            root_dir=Path(str(_require_key(trace, "root_dir", "trace.root_dir"))),
        ),
    )
