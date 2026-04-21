# Gazebo + ros2_control 细化设计（第一版）

## 1. 目标与范围
本设计针对当前平台中尚未落地的仿真与关键控制层，聚焦实现：
- Gazebo Harmonic 仿真世界
- TurtleBot 机器人模型接入
- ros2_control 控制闭环（`controller_manager + joint_state_broadcaster + diff_drive_controller`）
- 控制入口统一使用 `/cmd_vel`
- 与现有 runtime/trace 框架对接
- VEE 约束范围保持：Gazebo 在外，在线计算组件在内

本版目标是“可运行、可观测、可复现实验”，不是算法最优。

## 2. 已确认约束
### 2.1 技术栈
- 仿真栈：`Gazebo Harmonic + ROS 2 Jazzy + ros_gz_bridge`
- 运动学：`diff_drive`
- 模型来源：`TurtleBot`

### 2.2 场景与控制目标
- 场景：先固定一版“动态障碍密集” world
- 控制器组合：
  - `controller_manager`
  - `joint_state_broadcaster`
  - `diff_drive_controller`
- 控制指令入口：`/cmd_vel`

### 2.3 Bridge 覆盖范围
第一版 bridge 至少覆盖：
- 控制闭环：`/clock`、`/tf`、`/tf_static`、`/joint_states`、`/cmd_vel`
- 传感器：`lidar`、`camera`

### 2.4 VEE 边界
- VEE 外：Gazebo 仿真进程、REMOTE_API 服务端
- VEE 内：`runtime_scheduler`、`robot_control`、`agent_workers`

## 3. 模块化落地结构
采用“分层模块化”方案，目录职责如下：

1. `src/sim_description/`
- 保存 world、模型引用、机器人描述相关资源
- 第一版提供固定动态障碍密集 world

2. `src/sim_bringup/`
- 保存启动与桥接 launch
- 统一负责 Gazebo 启动、TurtleBot spawn、bridge 组装

3. `src/robot_control/`
- 保存 ros2_control 配置与控制节点
- 管理控制器生命周期（加载/激活）

4. `src/runtime_scheduler/`
- 复用现有窗口调度与 trace 机制
- 订阅仿真与控制状态用于 observation 组装

5. `src/infra/vee/`
- 复用并增强 VEE 约束注入逻辑
- 在启动流程中明确“哪些进程加入 VEE”

## 4. 运行拓扑与数据流
### 4.1 进程拓扑
1. Gazebo 进程（VEE 外）
2. `ros_gz_bridge`（由 bringup 管理）
3. `robot_control` 控制进程（VEE 内）
4. `runtime_scheduler`（VEE 内）
5. `agent_workers`（VEE 内）

### 4.2 控制闭环
1. 外部/测试节点向 `/cmd_vel` 发布
2. `diff_drive_controller` 接收并下发轮关节命令
3. `joint_state_broadcaster` 发布关节状态
4. TF 与里程计在 ROS 侧可观测
5. Gazebo 侧可视位姿变化与 ROS 状态一致

### 4.3 传感器链路
- lidar/camera 在 Gazebo 侧生成数据
- 通过 `ros_gz_bridge` 桥接至 ROS 话题
- 供 runtime/agent 后续消费（本版只需稳定可读）

## 5. 配置与启动设计
### 5.1 新增配置文件
建议新增：`experiment_configs/sim_gazebo_ros2_control.yaml`

最小字段：
```yaml
sim:
  backend: gazebo_harmonic
  world: dynamic_obstacle_dense
  use_sim_time: true

robot:
  model: turtlebot
  kinematics: diff_drive

bridge:
  enable_clock: true
  enable_tf: true
  enable_joint_states: true
  enable_cmd_vel: true
  enable_lidar: true
  enable_camera: true

control:
  controllers:
    - joint_state_broadcaster
    - diff_drive_controller
  cmd_vel_topic: /cmd_vel

vee:
  profile: edge_box_small
  apply_to:
    - runtime_scheduler
    - robot_control
    - agent_workers
```

### 5.2 控制器参数文件
在 `robot_control` 下提供控制器参数文件，至少包含：
- `controller_manager` 更新频率
- `joint_state_broadcaster` 基本配置
- `diff_drive_controller` 关键参数：轮距、轮半径、速度/加速度限制、cmd timeout

### 5.3 启动顺序（固定）
1. 启 Gazebo world（VEE 外）
2. spawn TurtleBot
3. 启 bridge（控制 + 传感器）
4. 启 `controller_manager` 并激活两个控制器
5. 启 `runtime_scheduler` 与既有 trace 流程
6. 运行 120s 实验并落盘 trace

## 6. 接口合同与可替换点
### 6.1 Bringup 接口
- 输入：world 名称、模型名、bridge 配置
- 输出：可用的 ROS 话题系统（含控制与传感器）

### 6.2 RobotControl 接口
- 输入：`/cmd_vel`
- 输出：`/joint_states`、相关 TF/里程计
- 状态接口：控制器 active 状态可查询

### 6.3 Runtime 接口
- 不直接依赖 Gazebo 内部 API
- 只依赖 ROS 话题与系统状态采样，保持调度模块独立性

## 7. 验收标准（Gazebo + ros2_control 专项）
满足以下条件视为本专项“跑通”：

1. 单命令启动后 60s 内进入可控状态
2. `joint_state_broadcaster` 与 `diff_drive_controller` 均为 active
3. 发布 `/cmd_vel` 后机器人在 Gazebo 中产生稳定运动
4. `/joint_states`、TF 连续更新
5. lidar/camera 话题可稳定接收
6. 与现有 runtime 共同运行时，120s 内持续写出 5 类 JSONL
7. 开启 VEE（Gazebo 外置）时，控制链路不崩溃且 trace 持续

## 8. 风险与缓解
1. Bridge 映射不一致导致控制/传感器断链
- 缓解：将话题映射集中在 bringup 单文件配置并加启动自检

2. `diff_drive_controller` 参数不当导致运动抖动
- 缓解：先保守速度上限，再逐步放开

3. Gazebo 与 ROS 时间源不一致
- 缓解：全链路显式启用 `use_sim_time` 并检查 `/clock`

4. VEE 约束过紧影响控制稳定性
- 缓解：对 `robot_control` 设最低保留预算，优先保障控制回路

## 9. 与现有 spec 的关系
本文件是对 [2026-04-21-runtime-platform-trace-design.md](/home/dawnat9/code-workspace/ai4heuristic/robotsim/docs/superpowers/specs/2026-04-21-runtime-platform-trace-design.md) 的“Gazebo + ros2_control 专项细化”。

若两者冲突，以本专项在仿真与控制层的具体约束为准；调度/trace 通用约束仍沿用原 spec。
