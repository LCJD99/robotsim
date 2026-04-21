from pathlib import Path

import pytest

from runtime_scheduler.config import load_config


BASELINE_CONFIG = Path("experiment_configs/v1_dynamic_dense.yaml")
FULL_CONFIG_TEXT = """
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
""".strip()


def test_load_config_reads_required_fields():
    cfg = load_config(BASELINE_CONFIG)

    assert cfg.experiment.duration_sec == 120
    assert cfg.experiment.id_format == "%Y%m%d-%H%M%S"
    assert cfg.scheduler.impl == "critical_first_fifo"
    assert cfg.scheduler.window_ms == 50
    assert cfg.agent_workload.generator == "poisson"
    assert cfg.agent_workload.seed == 42
    assert cfg.agent_workload.local_tool.lambda_per_sec == 4.0
    assert cfg.agent_workload.local_tool.max_arrivals_per_window == 8


@pytest.mark.parametrize(
    ("mutated_text", "missing_field"),
    [
        (FULL_CONFIG_TEXT.replace("  duration_sec: 120\n", ""), "experiment.duration_sec"),
        (FULL_CONFIG_TEXT.replace("  id_format: \"%Y%m%d-%H%M%S\"\n", ""), "experiment.id_format"),
        (FULL_CONFIG_TEXT.replace("  impl: critical_first_fifo\n", "", 1), "scheduler.impl"),
        (FULL_CONFIG_TEXT.replace("  window_ms: 50\n", ""), "scheduler.window_ms"),
        (
            FULL_CONFIG_TEXT.replace("  generator: poisson\n", ""),
            "agent_workload.generator",
        ),
        (FULL_CONFIG_TEXT.replace("  seed: 42\n", ""), "agent_workload.seed"),
        (
            FULL_CONFIG_TEXT.replace("    lambda_per_sec: 4.0\n", ""),
            "agent_workload.local_tool.lambda_per_sec",
        ),
        (
            FULL_CONFIG_TEXT.replace("    max_arrivals_per_window: 8\n", ""),
            "agent_workload.local_tool.max_arrivals_per_window",
        ),
    ],
)
def test_load_config_rejects_missing_required_keys(tmp_path, mutated_text, missing_field):
    path = tmp_path / "broken.yaml"
    path.write_text(mutated_text + "\n")

    with pytest.raises(ValueError, match=rf"^missing required key: {missing_field}$"):
        load_config(path)
