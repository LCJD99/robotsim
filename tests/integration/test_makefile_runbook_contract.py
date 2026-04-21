from pathlib import Path


def test_makefile_pins_colcon_and_launch_flow():
    makefile = Path("Makefile")
    assert makefile.exists()

    text = makefile.read_text(encoding="utf-8")
    assert "sim-build:" in text
    assert "sim-launch:" in text
    assert "colcon build" in text
    assert "source install/setup.bash" in text
    assert "ros2 launch sim_bringup sim_stack.launch.py" in text
