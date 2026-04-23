SHELL := /bin/bash

ROS_SETUP ?= /opt/ros/humble/setup.bash
COLCON_ARGS ?= --symlink-install
COLCON_BASE_PATHS ?= src
ROS_LOG_DIR ?= /tmp/roslog
LIBS_DIR ?= libs
HAMI_CORE_REPO ?= https://github.com/Project-HAMi/HAMi-core.git
HAMI_CORE_SRC ?= $(LIBS_DIR)/HAMi-core
HAMI_CORE_BUILD ?= $(HAMI_CORE_SRC)/build
HAMI_CORE_LIB ?= $(LIBS_DIR)/libvgpu.so

.PHONY: sim-build sim-launch sim-list-controllers sim-pub-cmd-vel \
	hami-core-clone hami-core-build hami-core-prepare vee-hami-smoke

sim-build:
	@bash -lc 'set -eo pipefail; source "$(ROS_SETUP)"; set -u; colcon build --base-paths "$(COLCON_BASE_PATHS)" $(COLCON_ARGS)'

sim-launch:
	@bash -lc 'set -eo pipefail; source "$(ROS_SETUP)"; source install/setup.bash; set -u; mkdir -p "$(ROS_LOG_DIR)"; export ROS_LOG_DIR="$(ROS_LOG_DIR)"; ros2 launch sim_bringup sim_stack.launch.py'

sim-list-controllers:
	@bash -lc 'set -eo pipefail; source "$(ROS_SETUP)"; source install/setup.bash; set -u; ros2 control list_controllers'

sim-pub-cmd-vel:
	@bash -lc 'set -eo pipefail; source "$(ROS_SETUP)"; source install/setup.bash; set -u; ros2 topic pub /cmd_vel geometry_msgs/msg/Twist "{linear: {x: 0.1}, angular: {z: 0.2}}" -r 10'

hami-core-clone:
	@bash -lc 'set -eo pipefail; mkdir -p "$(LIBS_DIR)"; \
		if [ ! -d "$(HAMI_CORE_SRC)/.git" ]; then \
			git clone "$(HAMI_CORE_REPO)" "$(HAMI_CORE_SRC)"; \
		else \
			echo "HAMi-core already exists at $(HAMI_CORE_SRC)"; \
		fi'

hami-core-build:
	@bash -lc 'set -eo pipefail; test -d "$(HAMI_CORE_SRC)"; \
		cmake -S "$(HAMI_CORE_SRC)" -B "$(HAMI_CORE_BUILD)"; \
		cmake --build "$(HAMI_CORE_BUILD)" -j"$$(nproc)"; \
		cp -f "$(HAMI_CORE_BUILD)/libvgpu.so" "$(HAMI_CORE_LIB)"; \
		echo "Built $(HAMI_CORE_LIB)"'

hami-core-prepare: hami-core-clone hami-core-build
	@echo "HAMi-core prepared: source=$(HAMI_CORE_SRC) lib=$(HAMI_CORE_LIB)"

vee-hami-smoke: hami-core-prepare
	@bash -lc 'set -eo pipefail; ./src/infra/vee/scripts/run_hami_container_smoke.sh'
