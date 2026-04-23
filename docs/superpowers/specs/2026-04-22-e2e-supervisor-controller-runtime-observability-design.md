# E2E Supervisor + 控制器运行时可观测设计（不含真实任务源接入）

## 1. 范围与目标

本设计仅覆盖以下三项，不包含“真实任务源接入”：

- 2) 实时运行与端到端编排（`e2e_runner.py`）
- 3) 控制器插件级精确周期观测接入 trace
- 4) 一键 E2E 运行、健康检查、回收与验收

目标是让任务调度器真正接入底层模拟器运行链路，并在 trace 中区分：

- 控制器真实执行性能（runtime/resource）
- 仿真语义稳定性（sim/control semantics）
- 数据链路延迟污染（late arrival）

## 2. 方案选择

采用方案 2：独立主进程 `e2e_runner.py` 进行编排。

原因：

- 边界清晰：仿真、控制、调度生命周期由单点管理
- 对现有模块侵入低：不要求将所有逻辑合并到同进程
- 便于失败诊断：主进程可统一落盘 run summary

## 3. 架构设计

### 3.1 主进程

新增 `src/runtime_scheduler/runtime_scheduler/e2e_runner.py`，负责：

1. 拉起 `ros2 launch sim_bringup sim_stack.launch.py`
2. 执行健康检查，确认 `joint_state_broadcaster` 与 `diff_drive_controller` 进入 `active`
3. 拉起 `runtime_scheduler.main`（实时模式）
4. 监听关键进程退出，统一停止与回收
5. 写入 `run_summary`（成功/失败原因、退出码、时长）

### 3.2 控制器观测链路（插件级）

允许修改 `src/robot_control`，在控制器插件路径增加周期原始指标发布。

每周期原始记录字段：

- `controller_name`
- `period_target_us`
- `cycle_start_sim_us`
- `cycle_end_sim_us`
- `cycle_period_sim_us`
- `cycle_start_mono_us`
- `cycle_end_mono_us`
- `exec_time_mono_us`
- `deadline_miss_exec`
- `late_start_sim`
- `late_finish_sim`
- `seq`

说明：

- `deadline_miss_exec` 判定：`exec_time_mono_us > exec_budget_us`
- 当前阶段 `exec_budget_us` 默认等于 `period_target_us`

### 3.3 Scheduler 聚合链路

scheduler 订阅控制器周期原始记录，按窗口聚合（粒度：每 window × 每 controller 1 条）。

输出聚合指标：

- `cycle_count`
- `exec_mono_us_p50/p95/max`
- `period_sim_us_p50/p95/max`
- `deadline_miss_exec_count`
- `late_start_sim_count`
- `late_finish_sim_count`
- `late_arrival_count`

## 4. 双时钟语义

### 4.1 语义时间（sim）

反映“仿真世界进展与控制语义稳定性”：

- `cycle_start_sim_us`
- `cycle_end_sim_us`
- `cycle_period_sim_us`

### 4.2 执行时间（mono）

反映“受限 CPU 真实执行耗时”：

- `cycle_start_mono_us`
- `cycle_end_mono_us`
- `exec_time_mono_us`

## 5. Trace 落盘与契约

新增 trace 文件：`controller_cycle_samples.jsonl`。

每条记录字段（窗口级聚合）：

- `schema_version`
- `experiment_id`
- `window_id`
- `timestamp_us`
- `controller_name`
- `period_target_us`
- `cycle_count`
- `exec_mono_us_p50`
- `exec_mono_us_p95`
- `exec_mono_us_max`
- `period_sim_us_p50`
- `period_sim_us_p95`
- `period_sim_us_max`
- `deadline_miss_exec_count`
- `late_start_sim_count`
- `late_finish_sim_count`
- `late_arrival_count`

## 6. 迟到与污染判定

- 窗口归属：默认按 `cycle_end_sim_us` 归属窗口
- `late_arrival_count`：记录到达聚合器时已超过其归属窗口统计封闭时刻
- 迟到记录不丢弃，计入对应窗口并打污染计数

## 7. 错误处理

### 7.1 启动阶段

- 控制器未 active 超时：启动失败，写 `run_summary` 并退出
- scheduler 启动失败：终止仿真子进程并退出

### 7.2 运行阶段

- 任一关键子进程异常退出：主进程触发全局终止
- 终止顺序：`SIGTERM -> timeout -> SIGKILL`
- 无论成功失败都写 `run_summary`

## 8. 验收标准

- `e2e_runner.py` 可一键拉起并收尾
- `controller_cycle_samples.jsonl` 按窗口与控制器稳定产出
- 压力场景下 `deadline_miss_exec_count` 可上升
- 人工注入延迟时 `late_arrival_count` 可上升
- scheduler trace 与 controller trace 可按 `window_id` 对齐

## 9. 非目标

- 不做真实任务源接入
- 不在本阶段引入多机器人控制器统计
- 不做 controller 预算策略自适应
