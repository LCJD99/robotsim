# Runtime 实验平台设计（第一版）

## 1. 背景与问题定义
本项目当前阶段的重点不是优化 scheduler 策略效果，而是搭建一个可复现实验平台，使其能够在具身混合 workload 场景下稳定运行并产出高质量 trace。

目标系统包含两类任务：
- 关键控制任务（如 ros2_control 控制回路）
- Agent 触发的非关键任务（第一版仅 LOCAL_TOOL）

平台需要在 Gazebo 动态障碍密集场景中运行，通过 VEE 对在线计算资源进行约束，执行基线调度并完整落盘 trace，为后续离线演化与消融提供数据基础。

## 2. 第一版目标与非目标
### 2.1 目标
- 跑通在线实验闭环：
  1. Gazebo 场景启动
  2. 关键控制任务持续运行
  3. 基线 scheduler 按窗口输出 plan
  4. LOCAL_TOOL 任务被调度执行
  5. 持续写出 observation/plan/outcome 等 JSONL
- VEE 资源约束生效：CPU + Memory + GPU（GPU 使用 hami-core）
- 生成按实验 ID 组织的 trace 目录，支持窗口级关联分析
- 运行参数全部配置化（YAML）
- 提供可配置的 Agent 任务发生器，第一版使用 Poisson 到达过程生成 `LOCAL_TOOL` 请求

### 2.2 非目标
- 不在第一版内覆盖 REMOTE_API 执行链路
- 不在第一版内追求最优调度指标

## 3. 已确认设计决策
### 3.1 调度与模式
- 在线基线 scheduler：`critical-first + FIFO`
- 模式切换机制：混合触发
  - runtime 负责升级到更保守模式
  - scheduler 仅可降级回去
  - 降级受 cooldown 控制
- 该触发机制必须模块化可替换，便于消融验证

### 3.2 安全与实验停止条件
- 安全相关指标保留为核心观测与比较指标
- 实验停止条件：固定时长，YAML 配置，第一版为 `120s`

### 3.3 VEE 与任务覆盖范围
- VEE 约束范围：除 Gazebo 外的全部在线计算组件
  - 包含 `runtime_scheduler`、`robot_control`、`agent_workers`
- API 任务的服务器端应在 VEE 外（第一版暂不执行 REMOTE_API）
- 第一版 Agent 任务仅覆盖：`LOCAL_TOOL`

### 3.4 控制层保真度
- 采用中等保真：`ros2_control` 基本控制回路 + 简化机器人模型

### 3.5 场景与资源画像
- 主验收场景：动态障碍密集
- 第一版只做 1 套 VEE profile
- profile 基于 `edge_box_small`，仅修改内存参数：
  - `memory.high = 6G`
  - `memory.max = 8G`
- 调度窗口：`50ms`

### 3.6 Trace 输出
- 最小必需文件（5 类）：
  - `window_observation.jsonl`
  - `plan.jsonl`
  - `outcome.jsonl`
  - `task_events.jsonl`
  - `resource_samples.jsonl`
- 目录按实验 ID 组织，实验 ID 按本地时间生成：`YYYYMMDD-HHMMSS`

### 3.7 Agent 任务发生模型
- 第一版新增 `AgentWorkloadGenerator` 模块
- 任务到达过程采用 Poisson 分布，并通过 YAML 显式配置
- 第一版仅生成 `LOCAL_TOOL` 任务
- 发生器支持固定随机种子，保证实验可复现

## 4. 方案对比与选型结论
已比较三类方案：
- 方案 1：ROS 优先最小闭环
- 方案 2：Runtime 中心化编排
- 方案 3：容器编排优先

最终采用方案 2（Runtime 中心化编排），原因：
- 更适合“平台先稳定、模块可替换做消融”的目标
- 策略模块与执行映射解耦，后续替换成本低
- 能在第一版保留可控工程复杂度与可复现性

## 5. 总体架构与运行边界
### 5.1 组件边界
- VEE 外：
  - Gazebo 仿真世界
  - REMOTE_API 服务端（为后续扩展预留）
- VEE 内：
  - `runtime_scheduler`
  - `robot_control`
  - `agent_workers`（第一版仅 LOCAL_TOOL）

### 5.2 运行时职责分离
- `runtime_scheduler`：窗口驱动编排、模式切换、策略调用、计划执行协调、trace 汇总
- `agent workload generator`：按配置生成 Agent 请求到达事件
- `robot_control`：关键控制循环（独立执行域）
- `agent_workers`：非关键工具任务执行（可限额/可回收）
- `telemetry/trace sink`：统一 schema 写入与目录管理

## 6. 模块化接口设计（用于消融）
第一版固定 6 个可替换模块位，统一由 runtime 装配：

1. `ModeTrigger`
- 输入：近期窗口安全/负载统计
- 输出：`NORMAL | CONSERVATIVE | DEGRADED | EMERGENCY`
- 规则：runtime 可强制升保守，scheduler 降级受 cooldown 约束

2. `PolicyCore`
- 输入：`SchedulerObservation + 当前 mode`
- 输出：`SchedulePlan`
- 第一版实现：`critical-first + FIFO`

3. `LaneMapper`
- 输入：`task_actions[].lane + vee profile`
- 输出：executor/cgroup/hami-core 具体映射
- 要求：映射逻辑固定在 runtime，不下放给 scheduler

4. `ExecutionAdapter`
- 职责：执行 plan、收集任务状态、汇总 outcome
- 要求：保证 observation-plan-outcome 的 `window_id` 一致

5. `TraceSink`
- 职责：按 schema/version 写 JSONL、滚动刷盘、失败可恢复
- 输出：5 类必需 trace 文件

6. `AgentWorkloadGenerator`
- 输入：窗口时长、当前场景状态、Poisson 参数配置
- 输出：当前窗口新到达的 `LOCAL_TOOL` 任务集合
- 第一版实现：Poisson arrival（`lambda_per_sec`），支持固定 seed 复现

## 7. 在线执行闭环
单次实验执行流程：
1. 读取 YAML 配置并生成 `experiment_id=YYYYMMDD-HHMMSS`
2. 创建目录：`traces/<experiment_id>/`
3. 启动 Gazebo 场景（动态障碍密集）
4. 启动 VEE 资源约束（对 runtime/control/agent 生效）
5. 启动 runtime 主循环（窗口 `50ms`）
   - 调用 `AgentWorkloadGenerator` 生成本窗口新到达任务
   - 采集 `SchedulerObservation`
   - 调用 `ModeTrigger`
   - 调用 `PolicyCore` 生成 `SchedulePlan`
   - 通过 `ExecutionAdapter` 执行并收集 `ScheduleOutcome`
   - TraceSink append 写入 JSONL
6. 到达 `duration_sec=120` 自动停止
7. 输出实验元数据与索引

## 8. 配置模型（YAML）
示例（第一版推荐默认值）：

```yaml
experiment:
  duration_sec: 120
  id_format: "%Y%m%d-%H%M%S"

scenario:
  type: dynamic_obstacle_dense

scheduler:
  impl: critical_first_fifo
  window_ms: 50

trigger:
  impl: hybrid
  cooldown_windows: 10

agent:
  enabled_task_types:
    - LOCAL_TOOL

agent_workload:
  generator: poisson
  seed: 42
  local_tool:
    lambda_per_sec: 4.0
    max_arrivals_per_window: 8

vee:
  profile: edge_box_small
  cpu:
    cpuset: "0-7"
    quota: "600000 1000000"
  memory:
    high: "6G"
    max: "8G"
  gpu:
    provider: hami-core
  network:
    delay_ms: 25
    jitter_ms: 5
    rate_mbps: 30
    loss_pct: 0.5

trace:
  root_dir: traces
  files:
    - window_observation.jsonl
    - plan.jsonl
    - outcome.jsonl
    - task_events.jsonl
    - resource_samples.jsonl
```

## 9. Trace 一致性约束
为保证后续可回放与可比较，第一版要求：
- `window_observation`、`plan`、`outcome` 三者共享：
  - `window_id`
  - `scheduler_version`
  - `policy_hash`
- 每条 `task_events` 能关联到 `window_id` 与 `task_id`
- 每条生成任务事件应带 `arrival_source=poisson` 与 `generator_seed`
- `resource_samples` 含统一时间戳字段，支持窗口归并
- 文件写入策略为 append-only JSONL

## 10. 第一版验收标准
满足以下条件即判定“平台跑通”：
1. 在动态障碍密集场景连续运行 120s，不崩溃
2. `robot_control` 控制循环持续运行且可观测
3. `LOCAL_TOOL` 任务在运行期间被调度并产生状态变化
4. VEE 资源约束实际生效（CPU/Memory/GPU）
5. `traces/<experiment_id>/` 下完整生成 5 类 JSONL 文件
6. 能基于 `window_id` 关联 observation/plan/outcome
7. `task_events` 中可观察到 Poisson 生成的到达事件元数据

## 11. 里程碑拆分（仅到平台完成）
- M1：配置与目录骨架完成（YAML + traces 组织）
- M2：VEE 约束链路打通（CPU/Memory + hami-core）
- M3：runtime 50ms 窗口闭环打通（obs/plan/outcome）
- M4：Poisson `AgentWorkloadGenerator` 接入并形成 task_events
- M5：LOCAL_TOOL 接入并形成可调度执行链路
- M6：120s 端到端实验回归通过并固化基线配置

## 12. 后续扩展边界（不属于本版）
- REMOTE_API 在线执行链路接入（服务端维持 VEE 外）
- 策略对比与消融实验矩阵扩大
- 离线 scheduler evolution 自动回放评估
