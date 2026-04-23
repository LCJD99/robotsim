# Online E2E Contract Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复调度-执行契约不一致，确保在线执行链路正确识别 RUN 与 lane，并统一 fallback trace 的 execution 字段。

**Architecture:** 保持调度输出契约不变（`decision` + `CRITICAL_LANE/CPU_LANE`），在执行适配器增加决策字段兼容与 lane 规范化映射。对 `run_experiment` 回退路径补 execution 占位，统一 trace 口径。通过最小回归测试锁定行为。

**Tech Stack:** Python 3.10, pytest, runtime_scheduler, telemetry trace JSONL.

---

## File Structure

- Modify: `src/runtime_scheduler/runtime_scheduler/execution_adapter.py`
- Modify: `src/runtime_scheduler/runtime_scheduler/main.py`
- Modify: `tests/runtime_scheduler/test_execution_adapter.py`
- Modify: `tests/runtime_scheduler/test_stepped_loop.py`
- Modify: `tests/integration/test_execution_trace_contract.py`

### Task 1: 修复 ExecutionAdapter 决策字段与 lane 映射

**Files:**
- Modify: `src/runtime_scheduler/runtime_scheduler/execution_adapter.py`
- Modify: `tests/runtime_scheduler/test_execution_adapter.py`

- [ ] **Step 1: 先写失败测试（decision + lane 规范化）**

```python
# tests/runtime_scheduler/test_execution_adapter.py

def test_execute_window_uses_decision_run_when_action_absent():
    ...
    task_actions=[{"task_id": "t1", "decision": "RUN", "lane": "CPU_LANE"}]
    ...


def test_execute_window_maps_scheduler_lane_to_config_lane():
    ...
    # CRITICAL_LANE -> critical, CPU_LANE -> high
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python3 -m pytest -q tests/runtime_scheduler/test_execution_adapter.py -k "decision or lane"`
Expected: FAIL.

- [ ] **Step 3: 实现最小修复**

```python
# execution_adapter.py
# 1) is_run = (decision == "RUN") or (action == "RUN")
# 2) normalize lane:
#    CRITICAL_LANE -> critical
#    CPU_LANE -> high
#    else -> fallback
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python3 -m pytest -q tests/runtime_scheduler/test_execution_adapter.py`
Expected: PASS.

- [ ] **Step 5: 提交**

```bash
git add src/runtime_scheduler/runtime_scheduler/execution_adapter.py tests/runtime_scheduler/test_execution_adapter.py
git commit -m "fix: align execution adapter with scheduler decision and lane contract"
```

### Task 2: 统一 fallback trace execution 占位

**Files:**
- Modify: `src/runtime_scheduler/runtime_scheduler/main.py`
- Modify: `tests/integration/test_execution_trace_contract.py`

- [ ] **Step 1: 写失败测试（fallback outcome 必含 execution mode）**

```python
# tests/integration/test_execution_trace_contract.py
# monkeypatch main.run_stepped_experiment -> raise ImportError
# run main.main() then read outcome.jsonl and assert:
# execution.mode == "offline_fallback"
# execution.success is False
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python3 -m pytest -q tests/integration/test_execution_trace_contract.py`
Expected: FAIL.

- [ ] **Step 3: 实现最小修复**

```python
# main.py in run_experiment path when writing outcome
outcome["execution"] = {
    "mode": "offline_fallback",
    "success": False,
    "reason": "gz_transport_unavailable",
}
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python3 -m pytest -q tests/integration/test_execution_trace_contract.py`
Expected: PASS.

- [ ] **Step 5: 提交**

```bash
git add src/runtime_scheduler/runtime_scheduler/main.py tests/integration/test_execution_trace_contract.py
git commit -m "fix: add offline fallback execution markers to outcome trace"
```

### Task 3: 补 stepped 路径回归断言（防回归）

**Files:**
- Modify: `tests/runtime_scheduler/test_stepped_loop.py`

- [ ] **Step 1: 补测试断言**

```python
# tests/runtime_scheduler/test_stepped_loop.py
# assert outcome has execution payload from adapter
# assert enforcement order unaffected
```

- [ ] **Step 2: 运行测试确认通过**

Run: `python3 -m pytest -q tests/runtime_scheduler/test_stepped_loop.py`
Expected: PASS.

- [ ] **Step 3: 提交**

```bash
git add tests/runtime_scheduler/test_stepped_loop.py
git commit -m "test: lock stepped-loop execution outcome contract"
```

## Minimal Validation Checklist

- [ ] `python3 -m pytest -q tests/runtime_scheduler/test_execution_adapter.py tests/runtime_scheduler/test_stepped_loop.py`
- [ ] `python3 -m pytest -q tests/integration/test_execution_trace_contract.py`

## Spec Coverage Review

- `decision/action` 契约：Task 1
- `CRITICAL_LANE/CPU_LANE` 映射：Task 1
- fallback `execution` 占位：Task 2
- 在线/离线路径 trace 口径一致：Task 2 + Task 3
