# Online E2E Contract Fix 设计说明（第一里程碑）

## 1. 背景

当前在线执行链路的主要阻断来自 `plan.task_actions` 与 `ExecutionAdapter` 的字段契约不一致：

- 调度输出使用 `decision`，执行侧读取 `action`
- 调度 lane 输出 `CRITICAL_LANE/CPU_LANE`，执行映射配置使用 `critical/high/best_effort/fallback`

这会导致 RUN 任务无法被正确识别，`/cmd_vel` 常走 stop/fallback 分支，影响在线端到端闭环。

## 2. 目标

本里程碑仅解决契约层阻断，保证在线执行链路可稳定触发。

- 以调度侧契约为准：`decision` + `CRITICAL_LANE/CPU_LANE`
- 运行时映射规则：
  - `CRITICAL_LANE -> critical`
  - `CPU_LANE -> high`（后续再细粒度）
- fallback 路径 (`run_experiment`) 的 trace 统一写 execution 占位：
  - `mode: offline_fallback`
  - `success: false`
  - `reason: "gz_transport_unavailable"`（或等价原因）
- 增加回归测试锁定上述契约

## 3. 非目标

- 本里程碑不处理更细粒度 lane 配置扩展
- 不改变调度策略排序逻辑（critical-first fifo）
- 不解决环境依赖（gz-transport/ROS2/cgroup/hami）

## 4. 设计方案

### 4.1 ExecutionAdapter 输入契约兼容

执行器改为以 `decision` 为主读取运行意图：

- `decision == "RUN"` 视为 RUN
- 仅当缺失 `decision` 时，兼容读取 `action`（过渡兼容，避免回归）

### 4.2 Lane 规范化映射

在执行器内增加规范化函数，将调度 lane 映射到配置键：

- `CRITICAL_LANE -> critical`
- `CPU_LANE -> high`
- 其他值 -> `fallback`

### 4.3 fallback trace 统一

`run_experiment` 写 `outcome` 时补充：

```json
"execution": {
  "mode": "offline_fallback",
  "success": false,
  "reason": "gz_transport_unavailable"
}
```

保证 stepped / fallback 两条路径都能产出可识别的 execution 字段。

## 5. 影响文件

- `src/runtime_scheduler/runtime_scheduler/execution_adapter.py`
- `src/runtime_scheduler/runtime_scheduler/main.py`
- `tests/runtime_scheduler/test_execution_adapter.py`
- `tests/runtime_scheduler/test_stepped_loop.py`
- `tests/integration/test_execution_trace_contract.py`

## 6. 验收标准

1. 调度输出仅有 `decision` 时，执行器仍能识别 RUN 并发布 motion。
2. `CPU_LANE` 映射使用 `high` 速度，`CRITICAL_LANE` 映射使用 `critical` 速度。
3. fallback 路径产生的 `outcome` 具备 `execution.mode=offline_fallback`。
4. 最小回归测试通过：
   - `tests/runtime_scheduler/test_execution_adapter.py`
   - `tests/runtime_scheduler/test_stepped_loop.py`
   - `tests/integration/test_execution_trace_contract.py`
