from pathlib import Path
import xml.etree.ElementTree as ET


def test_turtlebot_urdf_exists_and_contains_ros2_control_joints():
    urdf_path = Path("src/sim_description/urdf/turtlebot.urdf")
    assert urdf_path.exists()

    root = ET.fromstring(urdf_path.read_text(encoding="utf-8"))
    ros2_control = root.find("ros2_control")
    assert ros2_control is not None
    assert ros2_control.find("./hardware/plugin").text == "mock_components/GenericSystem"

    joints = {joint.attrib["name"] for joint in ros2_control.findall("./joint")}
    assert {"left_wheel_joint", "right_wheel_joint"} <= joints
