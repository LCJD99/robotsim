# Runtime Scheduler

Run the baseline runtime experiment with:

```bash
python -m runtime_scheduler.main
```

The run writes traces under `traces/<YYYYMMDD-HHMMSS>/` and produces five JSONL files:

- `window_observation.jsonl`
- `plan.jsonl`
- `outcome.jsonl`
- `task_events.jsonl`
- `resource_samples.jsonl`

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
