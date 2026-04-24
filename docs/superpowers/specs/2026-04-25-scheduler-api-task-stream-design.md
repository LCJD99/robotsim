# Scheduler API and Task Stream Design (v1)

Date: 2026-04-25

## 1. Goal and Scope

This spec defines API contracts for a scheduler that operates at `node` granularity and consumes task snapshots from a task stream.

This document defines contracts only:
- Object models
- API boundaries
- Merge semantics
- Idempotency and error semantics
- Registry guardrails

This document does not define scheduling strategy internals (for example: specific preemption policy, RL policy, or optimization algorithm).

## 2. Core Concepts

### 2.1 Task vs App

- `Task`: a dynamic execution instance triggered by one user request.
- `App`: a category/template of task flow.

Identity and classification:
- Primary identity is only `task_id`.
- `app_type` and `task_type` are classification fields.

Example:
- `task_id: eqa_0001`
- `app_type: perception_recognition_app`
- `task_type: recognize_objects`

### 2.2 Runtime Unit

- Scheduling unit is `node`.
- `node` and `edge` specs are globally defined in Registry.
- Task snapshots reference registry IDs rather than embedding full static specs.

## 3. API Topology

### 3.1 Registry API

Direction:
- `scheduler -> registry`

Purpose:
- Query static node/edge specs and bounds.

### 3.2 Observation API

Direction:
- `runtime/task-system -> scheduler`

Subscription:
- Same stream supports multi-subscriber fanout.
- `scheduler` and `trace logger` both subscribe to the same streams.

Structure:
- Snapshot Stream
- Event Stream

### 3.3 Control API

Direction:
- `scheduler -> runtime`

Purpose:
- Runtime control actions with mixed sync/async commands.

## 4. Observation API Contracts

## 4.1 Snapshot Stream

Method:
- `push_task_snapshot(TaskSnapshot)`

Rules:
- Snapshot is full-task snapshot for one `task_id` (not partial graph patch).
- Version rule per `task_id`: accept only `version > latest_seen_version`.
- `version <= latest_seen_version`: drop and emit `stale_snapshot` event.

`TaskSnapshot` fields:
- `task_id: string`
- `app_type: string`
- `task_type: string`
- `version: int`
- `timestamp_ms: int64`
- `task_state: pending | running | completed | failed | cancelled`
- `criticality: critical | non_critical`
- `node_refs: NodeRuntimeRef[]`
- `edge_refs: EdgeRuntimeRef[]`
- `overrides?: TaskOverrides`

`NodeRuntimeRef`:
- `node_id: string`
- `activation: required | optional`
- `priority: high | normal | null`
- `constraints_ref?: string`

Notes:
- `unused` is represented by omission from `node_refs`.

`EdgeRuntimeRef`:
- `edge_id: string`
- `activation: required | optional`
- `priority: high | normal | null`

Notes:
- Default edge activation is `required` when an edge appears in `edge_refs`.
- Edge priority defaults to destination node priority and may be overridden in snapshot.

`TaskOverrides` (optional, extensible):
- `node_priority_overrides: map<node_id, high|normal>`
- `edge_priority_overrides: map<edge_id, high|normal>`
- `policy_tags?: string[]`

## 4.2 Event Stream

Methods:
- `push_task_event(TaskEvent)`
- `push_runtime_state_event(RuntimeStateEvent)`
- `push_command_event(CommandEvent)`

`CommandEvent.status` enum:
- `accepted`
- `in_progress`
- `partially_applied`
- `succeeded`
- `failed`
- `cancelled`

Command event correlation:
- `command_id` is required.
- `task_id` is optional association metadata.

## 5. Active/Terminal Task Definitions

`active` task states:
- `pending`
- `running`

`terminal` task states:
- `completed`
- `failed`
- `cancelled`

Only active tasks participate in activation and priority merging.
Terminal tasks do not participate in merging.

## 6. Merge Semantics (Scheduler-side)

## 6.1 Node Activation Merge

For each node:
1. If `Registry.NodeSpec.core_always_on == true`, then `effective_activation = required`.
2. Otherwise merge across active tasks using precedence:
   - `required > optional > unused`

Operational implication:
- A node cannot be stopped while `effective_activation == required`.

## 6.2 Node Priority Merge

Base defaults:
- Task default: `critical -> high`, `non_critical -> normal`
- Node default: `Registry.NodeSpec.default_priority`

Override and merge:
- Snapshot override may replace defaults.
- Across active tasks for the same node: `high > normal`.

## 6.3 Edge Merge

Activation merge for same edge across active tasks:
- `required > optional`

Priority merge:
- Default follows destination node effective priority.
- Snapshot override may replace default.

## 7. Control API Contracts

## 7.1 Sync Commands

- `set_cpu_quota(node_id, quota)`
- `set_topic_rate(edge_id, hz)`
- `set_queue_depth(edge_id, depth)`
- `set_drop_policy(edge_id, policy)`
- `set_max_concurrency(node_id, n)`

## 7.2 Async Commands

- `start_node(node_id, command_id, task_id?)`
- `stop_node(node_id, command_id, task_id?)`
- `set_model_variant(node_id, variant, command_id, task_id?)`

Notes:
- Final start/stop decisions are based on merged global state from active tasks.
- A single task's local non-need must not directly imply global stop.

## 7.3 Error Model

Use common error code + extensible details:
- `INVALID_ARG`
- `NOT_FOUND`
- `CONFLICT`
- `TIMEOUT`
- `INTERNAL`

Extended details example:
- `details.bound_violation`
- `details.idempotency_conflict`

## 8. Idempotency

Primary idempotency key:
- `command_id`

Rules:
- Same `command_id` + same payload => must return same logical result.
- Same `command_id` + different payload => reject with idempotency conflict.
- `task_id` is optional association only, not part of idempotency key.

## 9. Registry API and Guardrails

## 9.1 Required Registry APIs

- `get_node_spec(node_id)`
- `list_node_specs(filter?)`
- `get_edge_spec(edge_id)`
- `list_edge_specs(filter?)`

## 9.2 NodeSpec

Required fields:
- `node_id: string`
- `core_always_on: bool`
- `default_priority: high | normal`
- `bounds`:
  - `cpu_quota: {min, max, default}`
  - `model_variant: {allowed[], default}`
  - `max_concurrency: {min, max, default}`

## 9.3 EdgeSpec

Required fields:
- `edge_id: string`
- `src_node_id: string`
- `dst_node_id: string`
- `bounds`:
  - `topic_rate: {min, max, default}`
  - `queue_depth: {min, max, default}`
  - `drop_policy: {allowed[], default}`

## 9.4 Validation Rule

All defaults come from Registry.
Runtime must not invent fallback defaults.

Control API must validate all incoming values against Registry bounds before execution.
Out-of-bounds requests must fail with common error code and `details.bound_violation`.

## 10. Non-goals for v1

- No scheduling algorithm internals
- No policy learning loop definition
- No transport-level protocol binding (for example: gRPC or REST)

This v1 focuses on stable logical contracts that can be mapped to any concrete protocol later.
