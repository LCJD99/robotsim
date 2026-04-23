from pathlib import Path

import yaml


def test_sim_stack_launch_mentions_robot_control_and_spawn_flow():
    launch_text = Path("src/sim_bringup/launch/sim_stack.launch.py").read_text(encoding="utf-8")

    assert "robot_control.launch.py" in launch_text
    assert "spawn" in launch_text.lower()
    assert 'LaunchConfiguration("gui")' in launch_text
    assert '"gui"' in launch_text
    assert 'default_value="false"' in launch_text
    assert "IfCondition" in launch_text
    assert "UnlessCondition" in launch_text
    assert "-s " in launch_text
    assert "-r " in launch_text


def test_dynamic_dense_experiment_declares_sim_block():
    config = yaml.safe_load(Path("experiment_configs/v1_dynamic_dense.yaml").read_text(encoding="utf-8"))

    assert config["sim"]["world_name"] == "dynamic_obstacle_dense"
    assert config["sim"]["physics_step_ms"] == 1
