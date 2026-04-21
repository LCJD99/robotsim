from pathlib import Path


def test_readme_contains_sim_runbook_and_acceptance_checks():
    text = Path("README.md").read_text(encoding="utf-8")

    assert "Gazebo + ros2_control bringup" in text
    assert "ros2 launch sim_bringup sim_stack.launch.py" in text
    assert "diff_drive_controller" in text
