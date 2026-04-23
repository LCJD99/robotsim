# ROS 控制器周期任务进入 trace 与调度 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

## Goal

将 ROS 控制器周期计算以任务形式注入每个调度窗口，写入 `task_events` 并参与 `plan/outcome`，覆盖 stepped、fallback、test 三条路径。

## Architecture

新增统一任务建模模块（建议 `runtime_scheduler/task_catalog.py`），封装：

- local-tool arrival -> task + event
- controller periodic task -> task + event

`main.py` 与 `stepped_loop.py` 仅做组装与写入，避免逻辑分叉。

## Tech Stack

- Python 3.10
- 现有 runtime_scheduler / telemetry trace 契约
- pytest

## File Structure

- Create: `src/runtime_scheduler/runtime_scheduler/task_catalog.py`
- Modify: `src/runtime_scheduler/runtime_scheduler/main.py`
- Modify: `src/runtime_scheduler/runtime_scheduler/stepped_loop.py`
- Modify: `tests/runtime_scheduler/test_stepped_loop.py`
- Modify: `tests/integration/test_execution_trace_contract.py`
- Optional Modify: `tests/integration/test_runtime_loop_smoke.py`

## Task 1: 新增任务建模与事件构造模块

- [ ] 定义固定控制器任务清单（2 个）
- [ ] 提供函数：
  - [ ] `build_controller_periodic_tasks(window_id, timestamp_us) -> list[dict]`
  - [ ] `build_controller_task_events(experiment_id, window_id, timestamp_us) -> list[dict]`
  - [ ] `build_local_tool_task(arrival) -> dict`
  - [ ] `build_local_tool_task_event(experiment_id, arrival) -> dict`
- [ ] 控制器事件字段满足现有 schema：`TASK_ARRIVAL` + `arrival_source/generator_seed/lambda_per_sec`

Verification:

- [ ] `python3 -m pytest -q tests/telemetry/test_schema_contract.py`

## Task 2: 三条运行路径接入控制器任务

- [ ] 在 `run_once_for_test` 中：
  - [ ] 追加控制器任务到 `tasks`
  - [ ] 写入控制器 `task_events`
- [ ] 在 `run_experiment` 中：
  - [ ] 每窗口追加控制器任务到 `tasks`
  - [ ] 每窗口写入控制器 `task_events`
- [ ] 在 `SteppedExperimentLoop.run` 中：
  - [ ] 每窗口追加控制器任务到 `tasks`
  - [ ] 每窗口写入控制器 `task_events`

Verification:

- [ ] `python3 -m pytest -q tests/runtime_scheduler/test_stepped_loop.py`
- [ ] `python3 -m pytest -q tests/integration/test_execution_trace_contract.py`

## Task 3: 补充/更新测试断言

- [ ] 新增 stepped loop 测试：断言传入 `run_single_window` 的 `tasks` 包含两个控制器任务且 `priority_class=HARD_CRITICAL`
- [ ] 更新 execution trace 合约测试：断言 `task_events` 出现 `task_type=ROS_CONTROLLER_CYCLE` 与 `source=controller_runtime`
- [ ] 如有必要，更新 smoke 测试最小断言（不绑定条数，只校验文件与关键字段）

Verification:

- [ ] `python3 -m pytest -q tests/runtime_scheduler/test_stepped_loop.py tests/integration/test_execution_trace_contract.py tests/integration/test_runtime_loop_smoke.py`

## Task 4: 全量回归

- [ ] 运行：`python3 -m pytest -q`
- [ ] 若失败，按失败用例最小修复，避免扩大改动面

## Done Criteria

- 三条路径均注入控制器周期任务
- 控制器任务在 `task_events`、`plan`、`outcome` 可观测
- 相关测试通过，并完成全量回归
