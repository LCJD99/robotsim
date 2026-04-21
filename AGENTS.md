# Repository Guidelines

## Project Structure & Module Organization
- `src/runtime_scheduler/runtime_scheduler/`: runtime loop, policy core, workload generation, config loading, experiment IDs.
- `src/telemetry/telemetry/`: trace schema, trace sink, resource sampling.
- `src/infra/vee/`: VEE adapter and runtime constraint scripts (`scripts/apply_runtime_constraints.sh`).
- `src/sim_description/`, `src/sim_bringup/`, `src/robot_control/`: Gazebo world/model assets, ROS 2 launch/bridge, and ros2_control setup.
- `tests/`: unit and integration contracts (`tests/integration/`, `tests/runtime_scheduler/`, `tests/sim_*`, `tests/robot_control/`, `tests/telemetry/`).
- `experiment_configs/`: runnable experiment YAMLs.
- `docs/superpowers/specs` and `docs/superpowers/plans`: design specs and implementation plans.

## Build, Test, and Development Commands
- `make sim-build`: build ROS 2 packages with `colcon build --symlink-install`.
- `make sim-launch`: source ROS and workspace, then run `ros2 launch sim_bringup sim_stack.launch.py`.
- `make sim-list-controllers`: verify `joint_state_broadcaster` and `diff_drive_controller`.
- `make sim-pub-cmd-vel`: publish a sample `/cmd_vel` command for motion checks.
- `python -m runtime_scheduler.main`: run baseline scheduler experiment and generate traces.
- `python3 -m pytest -q`: run full automated test suite.

## Coding Style & Naming Conventions
- Python target is `>=3.10`; use 4-space indentation and PEP 8 style.
- Prefer descriptive `snake_case` for functions, variables, modules, and config keys.
- Keep launch/config names explicit and scenario-oriented (example: `sim_stack.launch.py`, `v1_dynamic_dense.yaml`).
- Keep test files as `test_*.py`; align test name with contract being enforced.

## Testing Guidelines
- Framework: `pytest` (configured in `pyproject.toml` with `pythonpath` entries for `src/*` modules).
- Add or update tests with every behavior/config change, especially for launch and YAML contracts.
- Run focused tests during development, then run full suite before commit:
  - `python3 -m pytest -q tests/integration/test_sim_stack_config_contract.py`
  - `python3 -m pytest -q`

## Commit & Pull Request Guidelines
- Follow existing commit prefixes from history: `feat:`, `fix:`, `docs:`, `chore:`.
- Keep commits scoped to one logical change and include tests when behavior changes.
- PRs should include:
  - concise problem/solution summary,
  - touched modules and configs,
  - verification evidence (at least `pytest -q`; include launch checks when relevant).
