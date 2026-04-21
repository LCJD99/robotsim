from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description() -> LaunchDescription:
    world = LaunchConfiguration("world")
    bridge_config = PathJoinSubstitution([FindPackageShare("sim_bringup"), "config", "bridge_topics.yaml"])
    turtlebot_model = PathJoinSubstitution(
        [FindPackageShare("sim_description"), "models", "turtlebot", "model.sdf"]
    )
    robot_control = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution([FindPackageShare("robot_control"), "launch", "robot_control.launch.py"])
        )
    )
    spawn_turtlebot = Node(
        package="ros_gz_sim",
        executable="create",
        arguments=["-name", "turtlebot", "-file", turtlebot_model],
        output="screen",
    )

    gazebo = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution([FindPackageShare("ros_gz_sim"), "launch", "gz_sim.launch.py"])
        ),
        launch_arguments={"gz_args": ["-r ", world]}.items(),
    )

    bridge = Node(
        package="ros_gz_bridge",
        executable="parameter_bridge",
        name="ros_gz_parameter_bridge",
        parameters=[{"config_file": bridge_config}],
        output="screen",
    )

    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "world",
                default_value=PathJoinSubstitution(
                    [FindPackageShare("sim_description"), "worlds", "dynamic_obstacle_dense.sdf"]
                ),
            ),
            gazebo,
            bridge,
            spawn_turtlebot,
            robot_control,
        ]
    )
