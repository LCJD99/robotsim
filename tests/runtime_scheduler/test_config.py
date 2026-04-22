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

execution:
  cmd_vel_topic: /cmd_vel
  stop_on_non_run: true
  mapping:
    critical:
      linear_x: 0.20
      angular_z: 0.00
    high:
      linear_x: 0.12
      angular_z: 0.15
    best_effort:
      linear_x: 0.08
      angular_z: -0.10
    fallback:
      linear_x: 0.10
      angular_z: 0.00

sim:
  world_name: dynamic_obstacle_dense
  physics_step_ms: 1

vee:
  apply_to:
    - runtime_scheduler
    - robot_control
    - agent_workers
  enforcement_required: true
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
    assert cfg.execution.cmd_vel_topic == "/cmd_vel"
    assert cfg.execution.stop_on_non_run is True
    assert cfg.execution.mapping.critical.linear_x == pytest.approx(0.20)
    assert cfg.execution.mapping.critical.angular_z == pytest.approx(0.00)
    assert cfg.execution.mapping.high.linear_x == pytest.approx(0.12)
    assert cfg.execution.mapping.high.angular_z == pytest.approx(0.15)
    assert cfg.execution.mapping.best_effort.linear_x == pytest.approx(0.08)
    assert cfg.execution.mapping.best_effort.angular_z == pytest.approx(-0.10)
    assert cfg.execution.mapping.fallback.linear_x == pytest.approx(0.10)
    assert cfg.execution.mapping.fallback.angular_z == pytest.approx(0.00)
    assert cfg.sim.world_name == "dynamic_obstacle_dense"
    assert cfg.sim.physics_step_ms == 1
    assert cfg.vee.apply_to == ("runtime_scheduler", "robot_control", "agent_workers")
    assert cfg.vee.enforcement_required is True


def test_load_config_uses_sim_defaults_when_block_absent(tmp_path):
    path = tmp_path / "no_sim.yaml"
    path.write_text(FULL_CONFIG_TEXT.replace("\nsim:\n  world_name: dynamic_obstacle_dense\n  physics_step_ms: 1\n", "\n"))

    cfg = load_config(path)

    assert cfg.sim.world_name == "dynamic_obstacle_dense"
    assert cfg.sim.physics_step_ms == 1


def test_load_config_rejects_non_mapping_sim_block(tmp_path):
    path = tmp_path / "broken_sim.yaml"
    path.write_text(FULL_CONFIG_TEXT.replace("sim:\n  world_name: dynamic_obstacle_dense\n  physics_step_ms: 1\n", "sim: paused\n"))

    with pytest.raises(ValueError, match=r"^expected mapping at sim$"):
        load_config(path)


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
        (FULL_CONFIG_TEXT.replace("  cmd_vel_topic: /cmd_vel\n", ""), "execution.cmd_vel_topic"),
        (FULL_CONFIG_TEXT.replace("  stop_on_non_run: true\n", ""), "execution.stop_on_non_run"),
        (
            FULL_CONFIG_TEXT.replace(
                "    critical:\n      linear_x: 0.20\n      angular_z: 0.00\n",
                "",
                1,
            ),
            "execution.mapping.critical",
        ),
        (
            FULL_CONFIG_TEXT.replace(
                "    critical:\n      linear_x: 0.20\n      angular_z: 0.00\n",
                "    critical:\n      angular_z: 0.00\n",
                1,
            ),
            "execution.mapping.critical.linear_x",
        ),
        (
            FULL_CONFIG_TEXT.replace(
                "    critical:\n      linear_x: 0.20\n      angular_z: 0.00\n",
                "    critical:\n      linear_x: 0.20\n",
                1,
            ),
            "execution.mapping.critical.angular_z",
        ),
        (
            FULL_CONFIG_TEXT.replace(
                "    high:\n      linear_x: 0.12\n      angular_z: 0.15\n",
                "",
                1,
            ),
            "execution.mapping.high",
        ),
        (
            FULL_CONFIG_TEXT.replace(
                "    high:\n      linear_x: 0.12\n      angular_z: 0.15\n",
                "    high:\n      angular_z: 0.15\n",
                1,
            ),
            "execution.mapping.high.linear_x",
        ),
        (
            FULL_CONFIG_TEXT.replace(
                "    high:\n      linear_x: 0.12\n      angular_z: 0.15\n",
                "    high:\n      linear_x: 0.12\n",
                1,
            ),
            "execution.mapping.high.angular_z",
        ),
        (
            FULL_CONFIG_TEXT.replace(
                "    best_effort:\n      linear_x: 0.08\n      angular_z: -0.10\n",
                "",
                1,
            ),
            "execution.mapping.best_effort",
        ),
        (
            FULL_CONFIG_TEXT.replace(
                "    best_effort:\n      linear_x: 0.08\n      angular_z: -0.10\n",
                "    best_effort:\n      angular_z: -0.10\n",
                1,
            ),
            "execution.mapping.best_effort.linear_x",
        ),
        (
            FULL_CONFIG_TEXT.replace(
                "    best_effort:\n      linear_x: 0.08\n      angular_z: -0.10\n",
                "    best_effort:\n      linear_x: 0.08\n",
                1,
            ),
            "execution.mapping.best_effort.angular_z",
        ),
        (
            FULL_CONFIG_TEXT.replace(
                "    fallback:\n      linear_x: 0.10\n      angular_z: 0.00\n",
                "",
                1,
            ),
            "execution.mapping.fallback",
        ),
        (
            FULL_CONFIG_TEXT.replace(
                "    fallback:\n      linear_x: 0.10\n      angular_z: 0.00\n",
                "    fallback:\n      angular_z: 0.00\n",
                1,
            ),
            "execution.mapping.fallback.linear_x",
        ),
        (
            FULL_CONFIG_TEXT.replace(
                "    fallback:\n      linear_x: 0.10\n      angular_z: 0.00\n",
                "    fallback:\n      linear_x: 0.10\n",
                1,
            ),
            "execution.mapping.fallback.angular_z",
        ),
        (
            FULL_CONFIG_TEXT.replace(
                "  apply_to:\n    - runtime_scheduler\n    - robot_control\n    - agent_workers\n",
                "",
                1,
            ),
            "vee.apply_to",
        ),
        (
            FULL_CONFIG_TEXT.replace("  enforcement_required: true\n", ""),
            "vee.enforcement_required",
        ),
    ],
)
def test_load_config_rejects_missing_required_keys(tmp_path, mutated_text, missing_field):
    path = tmp_path / "broken.yaml"
    path.write_text(mutated_text + "\n")

    with pytest.raises(ValueError, match=rf"^missing required key: {missing_field}$"):
        load_config(path)
