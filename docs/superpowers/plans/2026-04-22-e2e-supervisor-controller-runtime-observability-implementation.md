# E2E Supervisor + 控制器运行时可观测 Implementation Plan（不含真实任务源）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

## Goal

完成调度器与底层模拟器的一键端到端接入，并补齐控制器插件级双时钟观测与窗口聚合 trace，覆盖运行保障与验收链路。

## Scope

只覆盖 2/3/4：

- `e2e_runner.py` 统一编排与生命周期管理
- 控制器插件级周期原始记录发布（sim + mono）
- scheduler 窗口聚合并写 `controller_cycle_samples.jsonl`

## Task 1: E2E Runner 编排主进程

Files:
- Create: `src/runtime_scheduler/runtime_scheduler/e2e_runner.py`
- Optional Modify: `Makefile`（新增 `sim-e2e` 目标）
- Test: `tests/integration/test_e2e_runner_contract.py`

Steps:
- [ ] 实现子进程拉起：`sim-launch` -> 健康检查 -> `runtime_scheduler.main`
- [ ] 实现健康检查（控制器 active）
- [ ] 实现统一回收（TERM/KILL）
- [ ] 输出 `run_summary`（json 或 jsonl）
- [ ] 新增 contract test（mock 子进程与健康检查）

Verification:
- [ ] `python3 -m pytest -q tests/integration/test_e2e_runner_contract.py`

## Task 2: 控制器插件级双时钟原始记录

Files:
- Modify: `src/robot_control/...`（控制器插件或其接入路径）
- Test: `tests/robot_control/test_controller_cycle_metrics_contract.py`

Steps:
- [ ] 在周期执行路径采集 `sim` 与 `mono` 时间戳
- [ ] 计算并发布字段：
  - [ ] `period_target_us`
  - [ ] `cycle_start_sim_us/cycle_end_sim_us/cycle_period_sim_us`
  - [ ] `cycle_start_mono_us/cycle_end_mono_us/exec_time_mono_us`
  - [ ] `deadline_miss_exec`
  - [ ] `late_start_sim`
  - [ ] `late_finish_sim`
- [ ] 默认规则：`exec_budget_us = period_target_us`
- [ ] 新增 contract test 校验字段完整性与数值关系

Verification:
- [ ] `python3 -m pytest -q tests/robot_control/test_controller_cycle_metrics_contract.py`

## Task 3: Scheduler 聚合与新 Trace 文件

Files:
- Modify: `src/runtime_scheduler/runtime_scheduler/stepped_loop.py`
- Create/Modify: `src/runtime_scheduler/runtime_scheduler/controller_cycle_aggregator.py`
- Modify: `src/telemetry/telemetry/schema_contract.py`
- Modify: `src/telemetry/telemetry/trace_sink.py`
- Test: `tests/runtime_scheduler/test_controller_cycle_aggregator.py`
- Test: `tests/telemetry/test_schema_contract.py`

Steps:
- [ ] 实现按 `(window_id, controller_name)` 聚合
- [ ] 产出指标：
  - [ ] `cycle_count`
  - [ ] `exec_mono_us_p50/p95/max`
  - [ ] `period_sim_us_p50/p95/max`
  - [ ] `deadline_miss_exec_count`
  - [ ] `late_start_sim_count`
  - [ ] `late_finish_sim_count`
  - [ ] `late_arrival_count`
- [ ] 新增 `controller_cycle_samples.jsonl` sink 映射
- [ ] 扩展 schema 校验

Verification:
- [ ] `python3 -m pytest -q tests/runtime_scheduler/test_controller_cycle_aggregator.py tests/telemetry/test_schema_contract.py`

## Task 4: 端到端验收与回归

Files:
- Test: `tests/integration/test_controller_cycle_samples_e2e_contract.py`
- Optional: `analysis/analyze_trace.py`（增加新文件摘要）

Steps:
- [ ] 新增 E2E 合约测试：窗口/控制器聚合记录存在
- [ ] 场景注入：CPU 压力（验证 `deadline_miss_exec_count` 上升）
- [ ] 场景注入：延迟污染（验证 `late_arrival_count` 上升）
- [ ] 全量回归

Verification:
- [ ] `python3 -m pytest -q tests/integration/test_controller_cycle_samples_e2e_contract.py`
- [ ] `python3 -m pytest -q`

## Done Criteria

- `e2e_runner.py` 可作为单入口稳定运行
- `controller_cycle_samples.jsonl` 契约稳定并可与现有 trace 按窗口对齐
- `deadline_miss_exec_count` 与 `late_arrival_count` 在注入场景下具备可观测性
- 全量测试通过
