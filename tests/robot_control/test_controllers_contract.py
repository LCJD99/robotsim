from pathlib import Path

import yaml


def test_required_controllers_defined_and_cmd_vel_used():
    cfg = yaml.safe_load(Path("src/robot_control/config/controllers.yaml").read_text(encoding="utf-8"))

    cm = cfg["controller_manager"]["ros__parameters"]
    assert "joint_state_broadcaster" in cm
    assert "diff_drive_controller" in cm

    ddc = cfg["diff_drive_controller"]["ros__parameters"]
    assert ddc["cmd_vel_timeout"] > 0.0
    assert ddc["base_frame_id"]


def test_robot_control_launch_wires_robot_description_for_controller_manager():
    launch_text = Path("src/robot_control/launch/robot_control.launch.py").read_text(encoding="utf-8")

    assert "robot_state_publisher" in launch_text
    assert "~/robot_description" in launch_text
    assert "/robot_description" in launch_text
