from pathlib import Path


def test_sim_stack_launch_mentions_robot_control_and_spawn_flow():
    launch_text = Path("src/sim_bringup/launch/sim_stack.launch.py").read_text(encoding="utf-8")

    assert "robot_control.launch.py" in launch_text
    assert "spawn" in launch_text.lower()
