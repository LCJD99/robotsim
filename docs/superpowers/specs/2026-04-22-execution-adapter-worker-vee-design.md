# Execution Adapter + Worker + VEE 一体化设计（Gap-1/2/3）

## 1. 背景与目标

基于 `docs/gaps.md` 中未实现缺口，本文定义一个可落地的一体化方案，覆盖：

- Gap-1：调度决策到 ROS 2 `/cmd_vel` 的物理控制链路
- Gap-2：Worker 物理负载与 `task_id -> pid` 映射
- Gap-3：VEE 运行时约束自动化挂载与动态 PID 注入

本设计优先级以“机器人可动闭环”为第一验收主线：
`task_actions -> /cmd_vel -> Gazebo 位姿变化`。

## 2. 范围与非目标

### 2.1 范围

- 在现有 `SteppedExperimentLoop` 基础上引入执行层（ExecutionAdapter）
- 实现按任务粒度的 Worker 进程停/恢（`SIGSTOP`/`SIGCONT`）
- 在启动阶段强制执行 VEE 约束，失败即中止
- Worker 启动后动态写入 `/sys/fs/cgroup/vee/cgroup.procs`
- 扩展 trace 中的执行结果字段，保证窗口级可审计

### 2.2 非目标

- 首版不实现复杂多机器人控制仲裁
- 首版不实现 GPU 强依赖负载（默认 CPU 负载）
- 首版不做策略学习，仅做规则映射与确定性执行

## 3. 总体架构

### 3.1 组件边界

1. `SteppedExperimentLoop`（已有）
- 仍是唯一编排器，固定时序：`sample -> plan -> execute -> step -> trace`
- 不承担 ROS2、信号、cgroup 细节

2. `ExecutionAdapter`（新增）
- 输入：窗口 `task_actions`
- 输出：
  - `/cmd_vel` 物理控制动作
  - Worker 进程控制动作
  - 结构化 outcome（供 trace 写入）

3. `WorkerManager`（新增）
- 管理 Worker 生命周期与 `task_id -> pid` 映射
- 暴露停/恢接口给 `ExecutionAdapter`

4. `VeeRuntimeEnforcer`（新增）
- 启动时执行 `apply_runtime_constraints.sh`（强制）
- Worker 拉起后将 PID 注入 `cgroup.procs`

5. `CmdVelPublisher`（新增，可作为 `ExecutionAdapter` 内部组件）
- 封装 ROS2 `Twist` 发布逻辑
- 提供 `publish_motion(vx, wz)` 与 `publish_stop()`

### 3.2 运行时数据流（单窗口）

1. `SteppedExperimentLoop` 产生 `task_actions`
2. 调用 `ExecutionAdapter.execute_window(...)`
3. `ExecutionAdapter` 选择 RUN 任务并发布 `/cmd_vel`；若无 RUN 则发布 0 速度
4. 对任务执行信号控制：RUN => `SIGCONT`，非 RUN => `SIGSTOP`
5. 若任务无 PID，则 `WorkerManager.ensure_workers(...)` 创建进程并调用 `VeeRuntimeEnforcer.attach_pid(pid)`
6. 返回 `execution_outcome`，并入 trace
7. `SimStepper.step(window_ms)` 推进仿真

## 4. 关键接口设计

### 4.1 ExecutionAdapter

```python
class ExecutionAdapter:
    def execute_window(
        self,
        task_actions: list[dict],
        now_ms: int,
    ) -> dict:
        """Apply cmd_vel + worker signals for one scheduler window.
        Returns outcome for trace: success/errors/affected_tasks.
        """
```

### 4.2 WorkerManager

```python
class WorkerManager:
    def ensure_workers(self, task_ids: list[str]) -> None: ...
    def get_pid(self, task_id: str) -> int | None: ...
    def stop_task(self, task_id: str) -> bool: ...      # SIGSTOP
    def resume_task(self, task_id: str) -> bool: ...    # SIGCONT
```

### 4.3 VeeRuntimeEnforcer

```python
class VeeRuntimeEnforcer:
    def enforce_startup(self) -> None: ...              # call script, fail-fast
    def attach_pid(self, pid: int) -> None: ...         # write cgroup.procs
```

### 4.4 CmdVelPublisher

```python
class CmdVelPublisher:
    def publish_motion(self, vx: float, wz: float) -> None: ...
    def publish_stop(self) -> None: ...
```

## 5. 规则映射（task_actions -> /cmd_vel）

### 5.1 决策规则

- 单机器人场景下，仅取“最高优先 RUN 任务”驱动速度
- 无 RUN 任务时执行安全停机：发布 `linear.x=0.0, angular.z=0.0`

### 5.2 默认 lane 映射

- `critical` -> `vx=0.20, wz=0.00`
- `high` -> `vx=0.12, wz=0.15`
- `best_effort` -> `vx=0.08, wz=-0.10`
- 未知 lane -> `vx=0.10, wz=0.00`

## 6. Worker 与 VEE 约束策略

### 6.1 Worker 负载模型（首版）

- 每个 `task_id` 对应独立 Worker 进程
- 默认 CPU 计算密集型负载（busy-loop 或可控矩阵计算）
- Worker 可通过信号停/恢，保证时间片执行可见

### 6.2 PID 注入流程

1. Worker 创建后拿到 PID
2. 写入 `/sys/fs/cgroup/vee/cgroup.procs`
3. 注入成功后才允许进入 RUN 态执行

### 6.3 启动约束

- 调度器启动阶段必须先执行 `apply_runtime_constraints.sh`
- 执行失败直接终止实验（Fail-Fast）

## 7. 错误处理与一致性约束

### 7.1 启动阶段硬失败

- `enforce_startup()` 失败：终止
- ROS2 发布器初始化失败：终止
- 首批 Worker 创建失败：终止

### 7.2 运行阶段窗口级失败记录

- 任务缺 PID：尝试一次 `ensure_workers([task_id])`；失败则记该任务失败
- 信号发送失败：记入 `worker_ops.err`，不阻断其他任务
- `/cmd_vel` 发布失败：窗口标记失败并尝试一次 `publish_stop()`
- cgroup 注入失败：记失败；若连续 3 窗口失败则终止

### 7.3 一致性要求

- 每个窗口必须写 `execution_outcome`
- 禁止“Worker RUN 与 robot STOP 且无错误记录”的静默不一致

## 8. Trace 扩展（建议）

在现有 trace schema 中追加执行侧字段：

- `execution.success: bool`
- `execution.cmd_vel: {vx, wz, reason}`
- `execution.worker_ops: [{task_id, pid, op, ok, err}]`
- `execution.enforcement: {attached_pids, failed_pids}`

## 9. 测试与验收

### 9.1 单元测试

- `ExecutionAdapter`
  - RUN 映射速度正确
  - 无 RUN 发布 stop
  - RUN/非 RUN 信号分派正确
- `WorkerManager`
  - `task_id -> pid` 建立/复用正确
  - 信号失败路径可观测
- `VeeRuntimeEnforcer`
  - 启动脚本失败即抛错
  - `attach_pid` 写入失败可观测

### 9.2 集成测试

- 单窗口执行后 trace 包含 `execution.cmd_vel` 与 `execution.worker_ops`
- 首次任务出现时执行 `attach_pid(pid)`
- 启动约束失败时主流程中止

### 9.3 端到端验收

- 有 RUN 的窗口：Gazebo 中机器人位姿在多个窗口后发生变化
- 全部非 RUN：机器人稳定停机（速度回零）
- trace 可回放每窗口的控制命令与进程控制结果

## 10. 实施分解建议

- Phase A（机器人可动闭环）
  - 实现 `CmdVelPublisher` + `ExecutionAdapter` 的规则映射
  - 补齐 `/cmd_vel` 到 trace 的执行回执
- Phase B（Worker + PID 映射）
  - 实现 `WorkerManager` 与按任务粒度信号控制
- Phase C（VEE 自动化）
  - 接入 `VeeRuntimeEnforcer.enforce_startup()` 与 `attach_pid()`
  - 增加连续失败阈值终止机制

## 11. 风险与缓解

- ROS2 发布抖动导致运动不稳定
  - 缓解：固定窗口发送频率 + stop 保底
- cgroup 写入权限问题
  - 缓解：启动前权限自检，失败快速退出
- Worker 信号风暴
  - 缓解：只在状态变化时发信号（同状态去重）

## 12. 通过标准（Definition of Done）

- 3 个 gap 均有对应代码路径与测试覆盖
- 主线验收“机器人可动闭环”通过
- `pytest -q` 全绿
- 运行日志/trace 可证明：计划、执行、步进三者时序一致
