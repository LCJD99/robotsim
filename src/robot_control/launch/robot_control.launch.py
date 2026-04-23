from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare
from launch.substitutions import PathJoinSubstitution


def generate_launch_description() -> LaunchDescription:
    controllers = PathJoinSubstitution([FindPackageShare("robot_control"), "config", "controllers.yaml"])
    urdf_path = Path(get_package_share_directory("sim_description")) / "urdf" / "turtlebot.urdf"
    robot_description = urdf_path.read_text(encoding="utf-8")

    robot_state_publisher = Node(
        package="robot_state_publisher",
        executable="robot_state_publisher",
        parameters=[{"robot_description": robot_description, "use_sim_time": True}],
        output="screen",
    )

    controller_manager = Node(
        package="controller_manager",
        executable="ros2_control_node",
        parameters=[controllers],
        remappings=[("~/robot_description", "/robot_description")],
        output="screen",
    )

    joint_state_broadcaster = Node(
        package="controller_manager",
        executable="spawner",
        arguments=[
            "joint_state_broadcaster",
            "--controller-manager",
            "/controller_manager",
            "--controller-manager-timeout",
            "120",
        ],
        output="screen",
    )

    diff_drive_controller = Node(
        package="controller_manager",
        executable="spawner",
        arguments=[
            "diff_drive_controller",
            "--controller-manager",
            "/controller_manager",
            "--controller-manager-timeout",
            "120",
        ],
        output="screen",
    )

    controller_cycle_metrics_publisher = Node(
        package="robot_control",
        executable="controller_cycle_metrics_publisher",
        output="screen",
        parameters=[
            {
                "topic": "/controller_cycle_metrics",
                "period_target_us": 20_000,
                "controller_names": [
                    "joint_state_broadcaster",
                    "diff_drive_controller",
                ],
            }
        ],
    )

    return LaunchDescription(
        [
            robot_state_publisher,
            controller_manager,
            joint_state_broadcaster,
            diff_drive_controller,
            controller_cycle_metrics_publisher,
        ]
    )
