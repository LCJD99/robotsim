# Trace Contract（在线评测 / Profiling）

本文档说明当前系统在“在线评测”运行时实际产出的 trace 结构，以及用于 profiling 分析时应遵守的字段合同。

合同来源（代码真相源）：
- `src/telemetry/telemetry/schema_contract.py`
- `src/telemetry/telemetry/trace_sink.py`
- `src/runtime_scheduler/runtime_scheduler/{main.py,stepped_loop.py,runtime_loop.py,task_catalog.py,controller_cycle_aggregator.py}`
- `tests/integration/test_execution_trace_contract.py`
- `tests/telemetry/test_schema_contract.py`

## 1. Trace 目录与文件

每次实验写入目录：
- `trace.root_dir/<experiment_id>/`

当前文件集合（JSONL，append-only）：
- `window_observation.jsonl`
- `plan.jsonl`
- `outcome.jsonl`
- `task_events.jsonl`
- `resource_samples.jsonl`
- `controller_cycle_samples.jsonl`

说明：每行是一个 JSON object，UTF-8 编码，`schema_version` 当前固定 `v1`。

## 2. 统一规则

1. 每条记录必须包含该 kind 对应的必填字段（见下节）。
2. `schema_version` 必须等于 `"v1"`。
3. 未知 kind 会被拒绝（`unknown trace kind`）。
4. 写入由 `TraceSink.write(kind, record)` 执行，先校验后落盘。

## 3. 各文件必填字段（强约束）

以下为 `validate_record()` 当前强制字段。

## 3.1 `window_observation.jsonl`

必填：
- `schema_version`
- `window_id`
- `timestamp_us`
- `scheduler_version`
- `policy_hash`

常见附加字段（运行时会写）：
- `task_count`

## 3.2 `plan.jsonl`

必填：
- `schema_version`
- `plan_id`
- `window_id`
- `generated_at_us`
- `scheduler_version`
- `policy_hash`

常见附加字段：
- `task_actions`（数组）
- `task_count`

`task_actions` 在当前策略下通常包含：
- `task_id`
- `decision`（例如 `RUN`）
- `lane`（`CRITICAL_LANE` / `CPU_LANE`）

## 3.3 `outcome.jsonl`

必填：
- `schema_version`
- `outcome_id`
- `window_id`
- `plan_id`
- `scheduler_version`
- `policy_hash`

常见附加字段：
- `task_count`
- `completed_task_ids`
- `execution`（在线 profiling 重点字段）

`execution` 在线路径（stepped loop）通常结构：
- `success: bool`
- `cmd_vel: { type, vx, wz }`
- `worker_ops: [...]`

离线回退路径（`gz transport` 不可用）会写：
- `execution = {"mode":"offline_fallback","success":false,"reason":"gz_transport_unavailable"}`

## 3.4 `task_events.jsonl`

必填：
- `schema_version`
- `experiment_id`
- `event_id`
- `event_type`
- `timestamp_us`
- `window_id`
- `task_id`
- `request_id`
- `task_type`
- `source`

额外条件（仅当 `event_type == "TASK_ARRIVAL"`）：
- `arrival_source`
- `generator_seed`
- `lambda_per_sec`

当前常见 `task_type`：
- `LOCAL_TOOL`
- `ROS_CONTROLLER_CYCLE`

## 3.5 `resource_samples.jsonl`

必填：
- `schema_version`
- `experiment_id`
- `sample_id`
- `timestamp_us`
- `window_id`
- `scope`
- `cpu`
- `memory`
- `gpu`
- `network`

当前常见子字段：
- `cpu.utilization_total`
- `memory.used_bytes`
- `memory.available_bytes`
- `gpu.utilization`
- `gpu.memory_used_bytes`
- `network.tx_rate_bps`
- `network.rx_rate_bps`

## 3.6 `controller_cycle_samples.jsonl`

必填：
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

## 4. 在线评测 Profiling 重点读法

建议以 `window_id` 做主键对齐：
- 调度输入：`window_observation`
- 调度决策：`plan.task_actions`
- 执行结果：`outcome.execution`
- 任务到达：`task_events`
- 资源背景：`resource_samples`
- 控制器时序质量：`controller_cycle_samples`

最常见 profiling 问题与对应文件：
- 为什么该窗口没有执行动作：`plan.jsonl` + `outcome.jsonl`
- 为什么动作执行失败或回退：`outcome.execution`
- 为什么控制链路抖动：`controller_cycle_samples.jsonl`
- 为什么资源受限：`resource_samples.jsonl`

## 5. 兼容性说明

1. 当前 contract 只对“必填字段 + schema_version”做强约束；允许附加字段。
2. 若新增字段，不应破坏现有必填集合。
3. 若新增 trace kind，需同步更新：
- `schema_contract.py` 的 `REQUIRED_KEYS`
- `trace_sink.py` 的 `KIND_TO_FILENAME`
- 对应测试（`tests/telemetry/test_schema_contract.py` / 集成合同测试）

## 6. 最小样例（示意）

```json
{"schema_version":"v1","window_id":"window-1","timestamp_us":1000000,"scheduler_version":"v1","policy_hash":"critical_first_fifo","task_count":3}
{"schema_version":"v1","plan_id":"plan-window-1","window_id":"window-1","generated_at_us":1000000,"scheduler_version":"v1","policy_hash":"critical_first_fifo","task_actions":[{"task_id":"controller-diff_drive_controller","decision":"RUN","lane":"CRITICAL_LANE"}]}
{"schema_version":"v1","outcome_id":"outcome-window-1","window_id":"window-1","plan_id":"plan-window-1","scheduler_version":"v1","policy_hash":"critical_first_fifo","execution":{"success":true,"cmd_vel":{"type":"motion","vx":0.4,"wz":0.1},"worker_ops":[{"op":"ensure","task_ids":["controller-diff_drive_controller"]}]}}
```

