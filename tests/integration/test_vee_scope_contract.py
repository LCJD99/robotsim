from pathlib import Path

import yaml


def test_vee_apply_to_targets_runtime_stack_not_gazebo():
    config = yaml.safe_load(Path("experiment_configs/v1_dynamic_dense.yaml").read_text(encoding="utf-8"))
    apply_to = config["vee"]["apply_to"]

    assert "gazebo" not in apply_to
    assert apply_to == ["runtime_scheduler", "robot_control", "agent_workers"]
