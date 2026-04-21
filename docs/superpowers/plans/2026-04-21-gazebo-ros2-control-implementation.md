# Gazebo + ros2_control Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a runnable Gazebo Harmonic + ROS 2 Jazzy simulation stack with TurtleBot diff_drive ros2_control loop, required ros_gz bridges, and integration points for the existing runtime/trace pipeline.

**Architecture:** Add three focused ROS packages: `sim_description` for world/model assets, `sim_bringup` for Gazebo/bridge orchestration, and `robot_control` for controller manager + controllers. Keep Gazebo outside VEE while runtime/control/worker components stay VEE-managed. Validate contracts in fast Python tests plus launch-level smoke checks, then run manual bringup validation.

**Tech Stack:** ROS 2 Jazzy, Gazebo Harmonic, ros_gz_bridge, ros2_control, diff_drive_controller, joint_state_broadcaster, Python pytest, YAML/SDF/Xacro assets.

---

## Scope Check
This plan covers one cohesive subsystem: **simulation + control-layer implementation for Gazebo/ros2_control**. It excludes scheduler policy evolution and REMOTE_API execution by design.

## File Structure

- Create: `src/sim_description/package.xml`
- Create: `src/sim_description/CMakeLists.txt`
- Create: `src/sim_description/worlds/dynamic_obstacle_dense.sdf`
- Create: `src/sim_description/launch/spawn_turtlebot.launch.py`
- Create: `src/sim_bringup/package.xml`
- Create: `src/sim_bringup/CMakeLists.txt`
- Create: `src/sim_bringup/config/bridge_topics.yaml`
- Create: `src/sim_bringup/launch/sim_stack.launch.py`
- Create: `src/robot_control/package.xml`
- Create: `src/robot_control/CMakeLists.txt`
- Create: `src/robot_control/config/controllers.yaml`
- Create: `src/robot_control/launch/robot_control.launch.py`
- Create: `src/infra/vee/scripts/apply_runtime_constraints.sh`
- Modify: `experiment_configs/v1_dynamic_dense.yaml`
- Modify: `README.md`
- Test: `tests/sim_description/test_world_contract.py`
- Test: `tests/sim_bringup/test_bridge_contract.py`
- Test: `tests/robot_control/test_controllers_contract.py`
- Test: `tests/integration/test_sim_stack_config_contract.py`

### Task 1: Build `sim_description` Package and Dynamic-Dense World

**Files:**
- Create: `src/sim_description/package.xml`
- Create: `src/sim_description/CMakeLists.txt`
- Create: `src/sim_description/worlds/dynamic_obstacle_dense.sdf`
- Create: `tests/sim_description/test_world_contract.py`

- [ ] **Step 1: Write failing world contract test**

```python
# tests/sim_description/test_world_contract.py
from pathlib import Path
import xml.etree.ElementTree as ET


def test_dynamic_dense_world_contains_many_dynamic_obstacles():
    world_path = Path("src/sim_description/worlds/dynamic_obstacle_dense.sdf")
    assert world_path.exists()

    root = ET.fromstring(world_path.read_text(encoding="utf-8"))
    models = root.findall(".//world/model")
    moving = [m for m in models if m.find("plugin[@name='moving_obstacle']") is not None]

    assert len(models) >= 12
    assert len(moving) >= 6
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/sim_description/test_world_contract.py -v`
Expected: FAIL with missing `dynamic_obstacle_dense.sdf`

- [ ] **Step 3: Create `sim_description` package skeleton**

```xml
<!-- src/sim_description/package.xml -->
<package format="3">
  <name>sim_description</name>
  <version>0.1.0</version>
  <description>Simulation worlds and robot description assets.</description>
  <maintainer email="dev@example.com">robotsim</maintainer>
  <license>Apache-2.0</license>
  <buildtool_depend>ament_cmake</buildtool_depend>
</package>
```

```cmake
# src/sim_description/CMakeLists.txt
cmake_minimum_required(VERSION 3.8)
project(sim_description)

find_package(ament_cmake REQUIRED)

install(DIRECTORY worlds launch
  DESTINATION share/${PROJECT_NAME}
)

ament_package()
```

- [ ] **Step 4: Add dynamic-dense world asset**

```xml
<!-- src/sim_description/worlds/dynamic_obstacle_dense.sdf -->
<sdf version="1.9">
  <world name="dynamic_obstacle_dense">
    <gravity>0 0 -9.8</gravity>
    <model name="ground_plane">
      <static>true</static>
      <link name="link">
        <collision name="collision">
          <geometry><plane><normal>0 0 1</normal><size>30 30</size></plane></geometry>
        </collision>
        <visual name="visual">
          <geometry><plane><normal>0 0 1</normal><size>30 30</size></plane></geometry>
        </visual>
      </link>
    </model>

    <model name="obstacle_01"><pose>2 2 0.5 0 0 0</pose><link name="l"><collision name="c"><geometry><box><size>0.5 0.5 1.0</size></box></geometry></collision><visual name="v"><geometry><box><size>0.5 0.5 1.0</size></box></geometry></visual></link></model>
    <model name="obstacle_02"><pose>3 -2 0.5 0 0 0</pose><link name="l"><collision name="c"><geometry><box><size>0.5 0.5 1.0</size></box></geometry></collision><visual name="v"><geometry><box><size>0.5 0.5 1.0</size></box></geometry></visual></link></model>
    <model name="obstacle_03"><pose>-2 3 0.5 0 0 0</pose><link name="l"><collision name="c"><geometry><box><size>0.5 0.5 1.0</size></box></geometry></collision><visual name="v"><geometry><box><size>0.5 0.5 1.0</size></box></geometry></visual></link></model>
    <model name="obstacle_04"><pose>-3 -3 0.5 0 0 0</pose><link name="l"><collision name="c"><geometry><box><size>0.5 0.5 1.0</size></box></geometry></collision><visual name="v"><geometry><box><size>0.5 0.5 1.0</size></box></geometry></visual></link></model>
    <model name="obstacle_05"><pose>0 4 0.5 0 0 0</pose><link name="l"><collision name="c"><geometry><box><size>0.5 0.5 1.0</size></box></geometry></collision><visual name="v"><geometry><box><size>0.5 0.5 1.0</size></box></geometry></visual></link></model>
    <model name="obstacle_06"><pose>4 0 0.5 0 0 0</pose><link name="l"><collision name="c"><geometry><box><size>0.5 0.5 1.0</size></box></geometry></collision><visual name="v"><geometry><box><size>0.5 0.5 1.0</size></box></geometry></visual></link></model>

    <model name="moving_01"><pose>1 1 0.2 0 0 0</pose><link name="l"><collision name="c"><geometry><cylinder><radius>0.2</radius><length>0.4</length></cylinder></geometry></collision><visual name="v"><geometry><cylinder><radius>0.2</radius><length>0.4</length></cylinder></geometry></visual></link><plugin name="moving_obstacle" filename="libMovingObstacle.so"/></model>
    <model name="moving_02"><pose>1 -1 0.2 0 0 0</pose><link name="l"><collision name="c"><geometry><cylinder><radius>0.2</radius><length>0.4</length></cylinder></geometry></collision><visual name="v"><geometry><cylinder><radius>0.2</radius><length>0.4</length></cylinder></geometry></visual></link><plugin name="moving_obstacle" filename="libMovingObstacle.so"/></model>
    <model name="moving_03"><pose>-1 1 0.2 0 0 0</pose><link name="l"><collision name="c"><geometry><cylinder><radius>0.2</radius><length>0.4</length></cylinder></geometry></collision><visual name="v"><geometry><cylinder><radius>0.2</radius><length>0.4</length></cylinder></geometry></visual></link><plugin name="moving_obstacle" filename="libMovingObstacle.so"/></model>
    <model name="moving_04"><pose>-1 -1 0.2 0 0 0</pose><link name="l"><collision name="c"><geometry><cylinder><radius>0.2</radius><length>0.4</length></cylinder></geometry></collision><visual name="v"><geometry><cylinder><radius>0.2</radius><length>0.4</length></cylinder></geometry></visual></link><plugin name="moving_obstacle" filename="libMovingObstacle.so"/></model>
    <model name="moving_05"><pose>2 0 0.2 0 0 0</pose><link name="l"><collision name="c"><geometry><cylinder><radius>0.2</radius><length>0.4</length></cylinder></geometry></collision><visual name="v"><geometry><cylinder><radius>0.2</radius><length>0.4</length></cylinder></geometry></visual></link><plugin name="moving_obstacle" filename="libMovingObstacle.so"/></model>
    <model name="moving_06"><pose>-2 0 0.2 0 0 0</pose><link name="l"><collision name="c"><geometry><cylinder><radius>0.2</radius><length>0.4</length></cylinder></geometry></collision><visual name="v"><geometry><cylinder><radius>0.2</radius><length>0.4</length></cylinder></geometry></visual></link><plugin name="moving_obstacle" filename="libMovingObstacle.so"/></model>
  </world>
</sdf>
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python3 -m pytest tests/sim_description/test_world_contract.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/sim_description tests/sim_description/test_world_contract.py
git commit -m "feat: add sim_description package and dynamic dense world"
```

### Task 2: Build `sim_bringup` Launch and Bridge Contracts

**Files:**
- Create: `src/sim_bringup/package.xml`
- Create: `src/sim_bringup/CMakeLists.txt`
- Create: `src/sim_bringup/config/bridge_topics.yaml`
- Create: `src/sim_bringup/launch/sim_stack.launch.py`
- Create: `tests/sim_bringup/test_bridge_contract.py`

- [ ] **Step 1: Write failing bridge contract test**

```python
# tests/sim_bringup/test_bridge_contract.py
from pathlib import Path
import yaml


def test_bridge_topics_cover_control_and_sensors():
    cfg = yaml.safe_load(Path("src/sim_bringup/config/bridge_topics.yaml").read_text(encoding="utf-8"))
    names = {entry["ros_topic_name"] for entry in cfg["bridges"]}

    required = {
        "/clock",
        "/cmd_vel",
        "/joint_states",
        "/tf",
        "/tf_static",
        "/scan",
        "/camera/image_raw",
    }
    assert required.issubset(names)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/sim_bringup/test_bridge_contract.py -v`
Expected: FAIL with missing bridge config file

- [ ] **Step 3: Create `sim_bringup` package skeleton**

```xml
<!-- src/sim_bringup/package.xml -->
<package format="3">
  <name>sim_bringup</name>
  <version>0.1.0</version>
  <description>Launch and bridge orchestration for Gazebo simulation stack.</description>
  <maintainer email="dev@example.com">robotsim</maintainer>
  <license>Apache-2.0</license>
  <buildtool_depend>ament_cmake</buildtool_depend>
  <exec_depend>ros_gz_bridge</exec_depend>
  <exec_depend>gazebo_ros</exec_depend>
</package>
```

```cmake
# src/sim_bringup/CMakeLists.txt
cmake_minimum_required(VERSION 3.8)
project(sim_bringup)

find_package(ament_cmake REQUIRED)

install(DIRECTORY launch config
  DESTINATION share/${PROJECT_NAME}
)

ament_package()
```

- [ ] **Step 4: Add bridge topic map and main launch**

```yaml
# src/sim_bringup/config/bridge_topics.yaml
bridges:
  - ros_topic_name: /clock
    gz_topic_name: /clock
    ros_type_name: rosgraph_msgs/msg/Clock
    gz_type_name: gz.msgs.Clock
    direction: GZ_TO_ROS
  - ros_topic_name: /cmd_vel
    gz_topic_name: /model/turtlebot/cmd_vel
    ros_type_name: geometry_msgs/msg/Twist
    gz_type_name: gz.msgs.Twist
    direction: ROS_TO_GZ
  - ros_topic_name: /joint_states
    gz_topic_name: /world/dynamic_obstacle_dense/model/turtlebot/joint_state
    ros_type_name: sensor_msgs/msg/JointState
    gz_type_name: gz.msgs.Model
    direction: GZ_TO_ROS
  - ros_topic_name: /tf
    gz_topic_name: /tf
    ros_type_name: tf2_msgs/msg/TFMessage
    gz_type_name: gz.msgs.Pose_V
    direction: GZ_TO_ROS
  - ros_topic_name: /tf_static
    gz_topic_name: /tf_static
    ros_type_name: tf2_msgs/msg/TFMessage
    gz_type_name: gz.msgs.Pose_V
    direction: GZ_TO_ROS
  - ros_topic_name: /scan
    gz_topic_name: /world/dynamic_obstacle_dense/model/turtlebot/link/lidar/scan
    ros_type_name: sensor_msgs/msg/LaserScan
    gz_type_name: gz.msgs.LaserScan
    direction: GZ_TO_ROS
  - ros_topic_name: /camera/image_raw
    gz_topic_name: /world/dynamic_obstacle_dense/model/turtlebot/link/camera/image
    ros_type_name: sensor_msgs/msg/Image
    gz_type_name: gz.msgs.Image
    direction: GZ_TO_ROS
```

```python
# src/sim_bringup/launch/sim_stack.launch.py
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description() -> LaunchDescription:
    world = LaunchConfiguration("world")

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
        arguments=["--ros-args", "--params-file", PathJoinSubstitution([FindPackageShare("sim_bringup"), "config", "bridge_topics.yaml"])],
        output="screen",
    )

    return LaunchDescription([
        DeclareLaunchArgument(
            "world",
            default_value=PathJoinSubstitution([FindPackageShare("sim_description"), "worlds", "dynamic_obstacle_dense.sdf"]),
        ),
        gazebo,
        bridge,
    ])
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python3 -m pytest tests/sim_bringup/test_bridge_contract.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/sim_bringup tests/sim_bringup/test_bridge_contract.py
git commit -m "feat: add sim_bringup package with bridge and launch"
```

### Task 3: Build `robot_control` with ros2_control Controllers

**Files:**
- Create: `src/robot_control/package.xml`
- Create: `src/robot_control/CMakeLists.txt`
- Create: `src/robot_control/config/controllers.yaml`
- Create: `src/robot_control/launch/robot_control.launch.py`
- Create: `tests/robot_control/test_controllers_contract.py`

- [ ] **Step 1: Write failing controller contract test**

```python
# tests/robot_control/test_controllers_contract.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/robot_control/test_controllers_contract.py -v`
Expected: FAIL with missing `controllers.yaml`

- [ ] **Step 3: Create `robot_control` package skeleton**

```xml
<!-- src/robot_control/package.xml -->
<package format="3">
  <name>robot_control</name>
  <version>0.1.0</version>
  <description>ros2_control bringup for TurtleBot diff drive.</description>
  <maintainer email="dev@example.com">robotsim</maintainer>
  <license>Apache-2.0</license>
  <buildtool_depend>ament_cmake</buildtool_depend>
  <exec_depend>controller_manager</exec_depend>
  <exec_depend>diff_drive_controller</exec_depend>
  <exec_depend>joint_state_broadcaster</exec_depend>
</package>
```

```cmake
# src/robot_control/CMakeLists.txt
cmake_minimum_required(VERSION 3.8)
project(robot_control)

find_package(ament_cmake REQUIRED)

install(DIRECTORY config launch
  DESTINATION share/${PROJECT_NAME}
)

ament_package()
```

- [ ] **Step 4: Add controllers config and launch**

```yaml
# src/robot_control/config/controllers.yaml
controller_manager:
  ros__parameters:
    update_rate: 50
    use_sim_time: true
    joint_state_broadcaster:
      type: joint_state_broadcaster/JointStateBroadcaster
    diff_drive_controller:
      type: diff_drive_controller/DiffDriveController

joint_state_broadcaster:
  ros__parameters:
    use_sim_time: true

diff_drive_controller:
  ros__parameters:
    use_sim_time: true
    left_wheel_names: ["left_wheel_joint"]
    right_wheel_names: ["right_wheel_joint"]
    wheel_separation: 0.287
    wheel_radius: 0.033
    cmd_vel_timeout: 0.5
    base_frame_id: base_footprint
    odom_frame_id: odom
    enable_odom_tf: true
    publish_rate: 50.0
    linear:
      x:
        has_velocity_limits: true
        max_velocity: 0.4
    angular:
      z:
        has_velocity_limits: true
        max_velocity: 1.2
```

```python
# src/robot_control/launch/robot_control.launch.py
from launch import LaunchDescription
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare
from launch.substitutions import PathJoinSubstitution


def generate_launch_description() -> LaunchDescription:
    controllers = PathJoinSubstitution([FindPackageShare("robot_control"), "config", "controllers.yaml"])

    cm = Node(
        package="controller_manager",
        executable="ros2_control_node",
        parameters=[controllers],
        output="screen",
    )

    jsb_spawner = Node(
        package="controller_manager",
        executable="spawner",
        arguments=["joint_state_broadcaster", "--controller-manager", "/controller_manager"],
        output="screen",
    )

    ddc_spawner = Node(
        package="controller_manager",
        executable="spawner",
        arguments=["diff_drive_controller", "--controller-manager", "/controller_manager"],
        output="screen",
    )

    return LaunchDescription([cm, jsb_spawner, ddc_spawner])
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python3 -m pytest tests/robot_control/test_controllers_contract.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/robot_control tests/robot_control/test_controllers_contract.py
git commit -m "feat: add robot_control package and ros2 controllers"
```

### Task 4: Integrate Simulation Stack Launch Contracts

**Files:**
- Modify: `src/sim_bringup/launch/sim_stack.launch.py`
- Create: `tests/integration/test_sim_stack_config_contract.py`

- [ ] **Step 1: Write failing integration contract test**

```python
# tests/integration/test_sim_stack_config_contract.py
from pathlib import Path


def test_sim_stack_launch_mentions_robot_control_and_spawn():
    launch_path = Path("src/sim_bringup/launch/sim_stack.launch.py")
    text = launch_path.read_text(encoding="utf-8")

    assert "robot_control.launch.py" in text
    assert "spawn" in text.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/integration/test_sim_stack_config_contract.py -v`
Expected: FAIL because launch does not include robot_control/spawn flow yet

- [ ] **Step 3: Extend sim stack launch with spawn + robot_control include**

```python
# key additions in src/sim_bringup/launch/sim_stack.launch.py
spawn_turtlebot = Node(
    package="ros_gz_sim",
    executable="create",
    arguments=[
        "-name", "turtlebot",
        "-topic", "/robot_description",
    ],
    output="screen",
)

robot_control = IncludeLaunchDescription(
    PythonLaunchDescriptionSource(
        PathJoinSubstitution([FindPackageShare("robot_control"), "launch", "robot_control.launch.py"])
    )
)

# and add both into LaunchDescription sequence after gazebo + bridge
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/integration/test_sim_stack_config_contract.py -v`
Expected: PASS

- [ ] **Step 5: Run relevant suite to verify no regressions**

Run: `python3 -m pytest tests/sim_description tests/sim_bringup tests/robot_control tests/integration/test_sim_stack_config_contract.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/sim_bringup/launch/sim_stack.launch.py tests/integration/test_sim_stack_config_contract.py
git commit -m "feat: wire spawn and robot_control into sim stack launch"
```

### Task 5: Add VEE Runtime Constraint Script and Config Wiring

**Files:**
- Create: `src/infra/vee/scripts/apply_runtime_constraints.sh`
- Modify: `experiment_configs/v1_dynamic_dense.yaml`
- Create: `tests/integration/test_vee_scope_contract.py`

- [ ] **Step 1: Write failing VEE scope test**

```python
# tests/integration/test_vee_scope_contract.py
from pathlib import Path
import yaml


def test_vee_scope_excludes_gazebo_and_includes_runtime_components():
    cfg = yaml.safe_load(Path("experiment_configs/v1_dynamic_dense.yaml").read_text(encoding="utf-8"))
    apply_to = set(cfg["vee"]["apply_to"])
    assert "gazebo" not in apply_to
    assert {"runtime_scheduler", "robot_control", "agent_workers"}.issubset(apply_to)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/integration/test_vee_scope_contract.py -v`
Expected: FAIL because `apply_to` list is absent

- [ ] **Step 3: Add VEE script and config scope**

```bash
# src/infra/vee/scripts/apply_runtime_constraints.sh
#!/usr/bin/env bash
set -euo pipefail

CGROUP_ROOT="/sys/fs/cgroup/vee"
CPUSET="${CPUSET:-0-7}"
CPU_MAX="${CPU_MAX:-600000 1000000}"
MEM_HIGH="${MEM_HIGH:-6G}"
MEM_MAX="${MEM_MAX:-8G}"

mkdir -p "$CGROUP_ROOT"
echo "$CPUSET" > "$CGROUP_ROOT/cpuset.cpus"
echo "$CPU_MAX" > "$CGROUP_ROOT/cpu.max"
echo "$MEM_HIGH" > "$CGROUP_ROOT/memory.high"
echo "$MEM_MAX" > "$CGROUP_ROOT/memory.max"

# GPU memory policy managed by hami-core
hami-core apply --group vee
```

```yaml
# append to experiment_configs/v1_dynamic_dense.yaml
vee:
  apply_to:
    - runtime_scheduler
    - robot_control
    - agent_workers
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/integration/test_vee_scope_contract.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/infra/vee/scripts/apply_runtime_constraints.sh experiment_configs/v1_dynamic_dense.yaml tests/integration/test_vee_scope_contract.py
git commit -m "feat: define vee apply scope for simulation runtime stack"
```

### Task 6: Document Runbook and Manual Acceptance Checks

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Write failing doc contract test**

```python
# tests/integration/test_readme_runbook_contract.py
from pathlib import Path


def test_readme_contains_sim_runbook_and_acceptance_checks():
    text = Path("README.md").read_text(encoding="utf-8")
    assert "Gazebo + ros2_control bringup" in text
    assert "ros2 launch sim_bringup sim_stack.launch.py" in text
    assert "diff_drive_controller" in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/integration/test_readme_runbook_contract.py -v`
Expected: FAIL until README is updated

- [ ] **Step 3: Add explicit runbook and acceptance checks**

```markdown
## Gazebo + ros2_control bringup

### Build
```bash
colcon build --symlink-install
source install/setup.bash
```

### Launch simulation stack
```bash
ros2 launch sim_bringup sim_stack.launch.py
```

### Verify controllers
```bash
ros2 control list_controllers
```
Expected: `joint_state_broadcaster` and `diff_drive_controller` are `active`.

### Send motion command
```bash
ros2 topic pub /cmd_vel geometry_msgs/msg/Twist "{linear: {x: 0.1}, angular: {z: 0.2}}" -r 10
```

### Acceptance checks
- Gazebo robot moves after `/cmd_vel`
- `/joint_states` updates continuously
- `/scan` and `/camera/image_raw` publish data
- `/clock` is available with sim time
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/integration/test_readme_runbook_contract.py -v`
Expected: PASS

- [ ] **Step 5: Run full suite for this feature set**

Run: `python3 -m pytest tests/sim_description tests/sim_bringup tests/robot_control tests/integration -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add README.md tests/integration/test_readme_runbook_contract.py
git commit -m "docs: add gazebo ros2_control runbook and acceptance checks"
```

## Final Verification Checklist
- [ ] `python3 -m pytest tests/sim_description tests/sim_bringup tests/robot_control tests/integration -v` passes
- [ ] `ros2 launch sim_bringup sim_stack.launch.py` starts Gazebo and bridge
- [ ] `ros2 control list_controllers` shows both required controllers active
- [ ] `/cmd_vel` command moves robot in simulation
- [ ] `/joint_states`, `/scan`, `/camera/image_raw`, `/clock` are observable
- [ ] VEE script applies to runtime/control/workers only (not Gazebo)

## Plan Self-Review
- Spec coverage:
  - Gazebo Harmonic + Jazzy + bridge: Task 2 + Task 4
  - TurtleBot + diff_drive: Task 3 + Task 4
  - Fixed dynamic-dense world: Task 1
  - `/cmd_vel` entry and controller trio: Task 3 + Task 6 validation
  - VEE boundary (Gazebo outside): Task 5
  - Sensor bridge (lidar/camera): Task 2 + Task 6 validation
- Placeholder scan: no TODO/TBD placeholders left.
- Type consistency: controller and topic names are consistent across tests, launch, and docs.
