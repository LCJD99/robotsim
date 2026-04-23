# ROS 控制器周期计算纳入 task_events 与调度设计

## 1. 背景

当前 trace 中 `task_events` 仅记录由 `PoissonLocalToolGenerator` 产生的 `LOCAL_TOOL` 任务，导致分析结果主要体现“用户/本地工具任务”，无法直接观察 ROS 控制器周期计算在窗口内的调度参与情况。

## 2. 目标

在不改变现有窗口调度主流程（`sample -> plan -> execute -> step -> trace`）的前提下，将 ROS 控制器自身周期计算建模为任务，并同时满足：

- 写入 `task_events`
- 参与 `plan.task_actions`
- 参与 `outcome.completed_task_ids`
- 在三条运行路径行为一致：
  - `run_stepped_experiment`
  - `run_experiment`（fallback）
  - `run_once_for_test`

## 3. 用户确认的约束

- 任务粒度：每个控制器每窗口 1 条任务
- 是否参与调度：参与
- 优先级：全部设为 `HARD_CRITICAL`
- 生效范围：三条运行路径一致

## 4. 方案

采用“每窗口注入控制器任务”的轻量方案（最小改动、最大复用）。

### 4.1 控制器任务定义

每个窗口固定注入以下任务：

- `controller-joint_state_broadcaster`
- `controller-diff_drive_controller`

属性：

- `priority_class = HARD_CRITICAL`
- `task_type = ROS_CONTROLLER_CYCLE`（用于 `task_events` 语义区分）

### 4.2 task_events 记录策略

控制器周期任务按 `TASK_ARRIVAL` 事件写入 `task_events`，并保留 schema 兼容字段：

- `source = controller_runtime`
- `arrival_source = periodic_controller`
- `generator_seed = -1`
- `lambda_per_sec = 0.0`

说明：当前 schema 对 `TASK_ARRIVAL` 统一要求 `arrival_source/generator_seed/lambda_per_sec`，因此控制器事件需补齐该三项。

### 4.3 调度参与方式

在每窗口构造 `tasks` 时：

1. 保留现有 local-tool 任务构造
2. 追加两个控制器任务
3. 统一交给 `run_single_window(...)`

由于现有策略已将 `HARD_CRITICAL` 映射为 `CRITICAL_LANE`，控制器任务无需新增策略逻辑即可优先进入关键车道。

## 5. 影响评估

### 5.1 正向影响

- Trace 可直接观测控制器周期任务到达与调度参与
- `plan/outcome` 的关键任务统计更贴近运行时现实
- 与既有策略和执行链路兼容，无需重构执行层

### 5.2 风险与缓解

- 风险：每窗口固定新增 2 条任务，trace 数量增长
- 缓解：当前仅 2 条/窗口，增量可控；分析脚本按计数聚合可兼容

## 6. 测试与验收

至少覆盖以下断言：

- `task_events` 包含 `ROS_CONTROLLER_CYCLE` 且 `source=controller_runtime`
- `plan.task_actions` 包含两个控制器任务，lane 为 `CRITICAL_LANE`
- 三条运行路径均注入控制器任务
- 现有 trace 契约测试保持通过

## 7. 非目标

- 本次不引入每物理 step 级别的控制器任务记录
- 本次不新增 controller 任务动态配置项
- 本次不改变 `ExecutionAdapter` 的控制输出语义

## 8. 完成标准

- 控制器周期任务在 `task_events`、`plan`、`outcome` 中可见
- 相关新增/更新测试通过
- `python3 -m pytest -q` 全绿（或至少相关测试集全绿并记录未执行项）
