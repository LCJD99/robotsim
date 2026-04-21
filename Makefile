SHELL := /bin/bash

ROS_SETUP ?= /opt/ros/humble/setup.bash
COLCON_ARGS ?= --symlink-install
ROS_LOG_DIR ?= /tmp/roslog

.PHONY: sim-build sim-launch sim-list-controllers sim-pub-cmd-vel

sim-build:
	@bash -lc 'set -euo pipefail; source "$(ROS_SETUP)"; colcon build $(COLCON_ARGS)'

sim-launch:
	@bash -lc 'set -euo pipefail; source "$(ROS_SETUP)"; source install/setup.bash; mkdir -p "$(ROS_LOG_DIR)"; export ROS_LOG_DIR="$(ROS_LOG_DIR)"; ros2 launch sim_bringup sim_stack.launch.py'

sim-list-controllers:
	@bash -lc 'set -euo pipefail; source "$(ROS_SETUP)"; source install/setup.bash; ros2 control list_controllers'

sim-pub-cmd-vel:
	@bash -lc 'set -euo pipefail; source "$(ROS_SETUP)"; source install/setup.bash; ros2 topic pub /cmd_vel geometry_msgs/msg/Twist "{linear: {x: 0.1}, angular: {z: 0.2}}" -r 10'
