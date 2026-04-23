# ARCH

## System Architecture

```mermaid
graph TD
    subgraph ENTRY[Entry / Orchestration]
        A1[make sim-launch]
        A2[python -m runtime_scheduler.main]
        A3[E2ERunner]
    end

    subgraph SIM[Simulation Module]
        B1[sim_description\nworld/model/URDF]
        B2[Gazebo (ros_gz_sim)]
    end

    subgraph ROS[ROS Control Module]
        C1[sim_bringup launch]
        C2[ros_gz_bridge]
        C3[robot_control launch]
        C4[ros2_control\ncontroller_manager + controllers]
        C5[controller_cycle_metrics_publisher\n/controller_cycle_metrics]
    end

    subgraph SCHED[Scheduler Module]
        D1[runtime_scheduler.main]
        D2[Stepped/Fallback Loop]
        D3[Policy + ExecutionAdapter]
        D4[CmdVelPublisher\n/cmd_vel]
        D5[ControllerCycleSource + Aggregator]
    end

    subgraph VEE[VEE Module]
        E1[VeeRuntimeEnforcer]
        E2[apply_runtime_constraints.sh]
        E3[cgroup attach / runtime limits]
    end

    subgraph OBS[Telemetry Module]
        F1[TraceSink + SchemaContract]
        F2[window_observation / plan / outcome]
        F3[task_events / resource_samples]
        F4[controller_cycle_samples]
    end

    A1 --> C1
    A2 --> D1
    A3 --> C1
    A3 --> D1

    B1 --> B2
    C1 --> B2
    C1 --> C2
    C1 --> C3
    C3 --> C4
    C3 --> C5

    D1 --> D2
    D2 --> D3
    D3 --> D4
    C5 --> D5
    D5 --> D2

    D2 --> F1
    F1 --> F2
    F1 --> F3
    F1 --> F4

    D1 --> E1
    E1 --> E2
    E1 --> E3
    E3 -. constrain .-> D1
    E3 -. constrain .-> C4

    %% Color styles
    classDef entry fill:#E8F1FF,stroke:#3B82F6,stroke-width:1.5px,color:#0B2545;
    classDef sim fill:#EAFBF0,stroke:#22A06B,stroke-width:1.5px,color:#123524;
    classDef ros fill:#FFF4E5,stroke:#F59E0B,stroke-width:1.5px,color:#4A2C00;
    classDef sched fill:#F3E8FF,stroke:#8B5CF6,stroke-width:1.5px,color:#2E1065;
    classDef vee fill:#FFEAEA,stroke:#DC2626,stroke-width:1.5px,color:#4B1010;
    classDef obs fill:#E6FFFB,stroke:#0D9488,stroke-width:1.5px,color:#083B35;

    class A1,A2,A3 entry;
    class B1,B2 sim;
    class C1,C2,C3,C4,C5 ros;
    class D1,D2,D3,D4,D5 sched;
    class E1,E2,E3 vee;
    class F1,F2,F3,F4 obs;
```

## Module Overview

## ASCII Architecture

```text
+---------------------------- Entry / Orchestration ----------------------------+
| [make sim-launch]   [python -m runtime_scheduler.main]   [E2ERunner]         |
+-------------------------------+----------------------------+-------------------+
                                |                            |
                                v                            v
+---------------------------- ROS Control Module -------------------------------+
| sim_bringup launch --> ros_gz_bridge --> robot_control launch               |
|                                        |                                     |
|                                        +--> ros2_control (controller_manager)|
|                                        +--> controller_cycle_metrics_publisher|
|                                             (/controller_cycle_metrics)        |
+-------------------------------+----------------------------+-------------------+
                                |                            ^
                                | /cmd_vel                   | controller metrics
                                v                            |
+--------------------------- Simulation Module -------------------------------+  |
| sim_description (world/model/URDF) --> Gazebo (ros_gz_sim)                |  |
+----------------------------------------+------------------------------------+  |
                                         |                                       |
                                         v                                       |
+--------------------------- Scheduler Module -----------------------------------+
| runtime_scheduler.main -> Stepped/Fallback Loop -> Policy+ExecutionAdapter    |
|                                              |                                  |
|                                              +-> CmdVelPublisher (/cmd_vel)     |
|                                              +-> ControllerCycleSource+Aggregator|
+-------------------------------+-------------------------------------------------+
                                |
                                v
+--------------------------- Telemetry Module -----------------------------------+
| TraceSink + SchemaContract                                                     |
|  - window_observation.jsonl                                                   |
|  - plan.jsonl                                                                 |
|  - outcome.jsonl                                                              |
|  - task_events.jsonl                                                          |
|  - resource_samples.jsonl                                                     |
|  - controller_cycle_samples.jsonl                                             |
+--------------------------------------------------------------------------------+

+------------------------------ VEE Module --------------------------------------+
| VeeRuntimeEnforcer -> apply_runtime_constraints.sh -> cgroup runtime limits    |
| (constrains runtime_scheduler + ros2_control workers/processes)                |
+--------------------------------------------------------------------------------+
```

- `src/sim_description/`
  - 仿真资产层，提供世界文件、机器人模型与 URDF，定义 Gazebo 中的物理环境与机器人结构。

- `src/sim_bringup/`
  - 仿真编排层，启动 Gazebo、ROS-Gazebo bridge、机器人生成与 `robot_control` 子系统。

- `src/robot_control/`
  - 控制执行层，负责 `ros2_control` 控制器启动（`joint_state_broadcaster`、`diff_drive_controller`）以及控制器周期指标发布（`/controller_cycle_metrics`）。

- `src/runtime_scheduler/runtime_scheduler/`
  - 调度核心层。
  - `main.py`：主入口，负责 stepped/fallback 运行模式、VEE 接入、执行器与 trace 写入。
  - `stepped_loop.py`：窗口循环编排（采样 -> 任务生成 -> 策略 -> 执行 -> trace）。
  - `workload_generator.py`：本地工具任务到达生成（Poisson）。
  - `task_catalog.py`：任务/事件建模（含控制器周期任务注入）。
  - `runtime_loop.py` + `policy_core.py`：窗口内策略决策与 lane 分配。
  - `execution_adapter.py`：把策略动作映射到 `/cmd_vel` 和 worker 控制操作。
  - `worker_manager.py` + `worker_process.py`：任务级 worker 进程生命周期管理。
  - `vee_runtime_enforcer.py`：VEE 约束启动与 PID 挂载。
  - `controller_cycle_source.py`：从 ROS topic 读取控制器周期原始记录。
  - `controller_cycle_aggregator.py`：按 `window_id x controller_name` 聚合指标。
  - `e2e_runner.py`：可选 supervisor，统一拉起仿真与调度进程并回收。

- `src/telemetry/telemetry/`
  - 观测与落盘层。
  - `trace_sink.py`：统一 JSONL trace 输出。
  - `schema_contract.py`：trace 记录契约校验。
  - `resource_sampler.py` / `real_resource_sampler.py`：系统资源采样。

- `src/infra/vee/`
  - 资源约束基础设施层，提供约束脚本与适配逻辑（CPU/内存/GPU 运行时限制）。

- `experiment_configs/`
  - 实验配置层，定义窗口大小、任务负载、执行映射、仿真参数、VEE 参数与 trace 根目录。

- `analysis/analyze_trace.py`
  - 离线分析层，对 trace 做窗口级任务流统计与异常检查，输出报告。

## Runtime Paths

- 仿真控制路径
  - `make sim-launch` 启动 `sim_bringup`，仅负责仿真与控制栈，不直接驱动调度 trace。

- 调度实验路径
  - `python -m runtime_scheduler.main` 启动调度与 trace 管线。
  - 优先尝试 stepped 模式（与仿真步进对齐）；若缺少 `gz-transport`，自动 fallback 到 wall-clock 批处理模式。

- 端到端编排路径（可选）
  - `runtime_scheduler.e2e_runner` 作为 supervisor 统一管理仿真与调度进程生命周期。
