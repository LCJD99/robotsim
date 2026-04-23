from runtime_scheduler.execution_adapter import ExecutionAdapter


class FakeCmdVelPublisher:
    def __init__(self) -> None:
        self.calls: list[tuple[str, float, float]] = []

    def publish_motion(self, vx: float, wz: float) -> None:
        self.calls.append(("motion", vx, wz))

    def publish_stop(self) -> None:
        self.calls.append(("stop", 0.0, 0.0))


def test_execute_window_run_maps_cpu_lane_to_high_velocity_and_resumes_task() -> None:
    publisher = FakeCmdVelPublisher()
    ensured: list[list[str]] = []
    resumed: list[str] = []
    stopped: list[str] = []

    adapter = ExecutionAdapter(
        cmd_vel_publisher=publisher,
        ensure=ensured.append,
        resume=resumed.append,
        stop=stopped.append,
        velocity_mapping={"high": (0.25, 0.1), "fallback": (0.0, 0.0)},
    )

    result = adapter.execute_window(
        task_actions=[{"task_id": "task-a", "action": "RUN", "lane": "CPU_LANE"}],
        now_ms=123,
    )

    assert ensured == [["task-a"]]
    assert resumed == ["task-a"]
    assert stopped == []
    assert publisher.calls == [("motion", 0.25, 0.1)]
    assert result == {
        "success": True,
        "cmd_vel": {"type": "motion", "vx": 0.25, "wz": 0.1},
        "worker_ops": [
            {"op": "ensure", "task_ids": ["task-a"]},
            {"op": "resume", "task_id": "task-a"},
        ],
    }


def test_execute_window_non_run_only_publishes_stop() -> None:
    publisher = FakeCmdVelPublisher()
    ensured: list[list[str]] = []
    resumed: list[str] = []
    stopped: list[str] = []

    adapter = ExecutionAdapter(
        cmd_vel_publisher=publisher,
        ensure=ensured.append,
        resume=resumed.append,
        stop=stopped.append,
        velocity_mapping={"CPU_LANE": (0.25, 0.1), "fallback": (0.0, 0.0)},
    )

    result = adapter.execute_window(
        task_actions=[
            {"task_id": "task-a", "action": "STOP", "lane": "CPU_LANE"},
            {"task_id": "task-b", "action": "PAUSE", "lane": "CPU_LANE"},
        ],
        now_ms=456,
    )

    assert ensured == [["task-a", "task-b"]]
    assert resumed == []
    assert stopped == ["task-a", "task-b"]
    assert publisher.calls == [("stop", 0.0, 0.0)]
    assert result == {
        "success": True,
        "cmd_vel": {"type": "stop", "vx": 0.0, "wz": 0.0},
        "worker_ops": [
            {"op": "ensure", "task_ids": ["task-a", "task-b"]},
            {"op": "stop", "task_id": "task-a"},
            {"op": "stop", "task_id": "task-b"},
        ],
    }


def test_execute_window_unknown_lane_uses_fallback_velocity() -> None:
    publisher = FakeCmdVelPublisher()
    ensured: list[list[str]] = []
    resumed: list[str] = []
    stopped: list[str] = []

    adapter = ExecutionAdapter(
        cmd_vel_publisher=publisher,
        ensure=ensured.append,
        resume=resumed.append,
        stop=stopped.append,
        velocity_mapping={"critical": (0.4, 0.2), "fallback": (0.1, -0.1)},
    )

    result = adapter.execute_window(
        task_actions=[{"task_id": "task-z", "action": "RUN", "lane": "UNKNOWN_LANE"}],
        now_ms=789,
    )

    assert ensured == [["task-z"]]
    assert resumed == ["task-z"]
    assert stopped == []
    assert publisher.calls == [("motion", 0.1, -0.1)]
    assert result["cmd_vel"] == {"type": "motion", "vx": 0.1, "wz": -0.1}


def test_execute_window_decision_run_works_when_action_absent() -> None:
    publisher = FakeCmdVelPublisher()
    ensured: list[list[str]] = []
    resumed: list[str] = []
    stopped: list[str] = []

    adapter = ExecutionAdapter(
        cmd_vel_publisher=publisher,
        ensure=ensured.append,
        resume=resumed.append,
        stop=stopped.append,
        velocity_mapping={"high": (0.3, 0.0), "fallback": (0.0, 0.0)},
    )

    result = adapter.execute_window(
        task_actions=[{"task_id": "task-decision", "decision": "RUN", "lane": "CPU_LANE"}],
        now_ms=1000,
    )

    assert ensured == [["task-decision"]]
    assert resumed == ["task-decision"]
    assert stopped == []
    assert publisher.calls == [("motion", 0.3, 0.0)]
    assert result["cmd_vel"] == {"type": "motion", "vx": 0.3, "wz": 0.0}


def test_execute_window_run_maps_critical_lane_to_critical_velocity() -> None:
    publisher = FakeCmdVelPublisher()
    ensured: list[list[str]] = []
    resumed: list[str] = []
    stopped: list[str] = []

    adapter = ExecutionAdapter(
        cmd_vel_publisher=publisher,
        ensure=ensured.append,
        resume=resumed.append,
        stop=stopped.append,
        velocity_mapping={"critical": (0.6, 0.4), "fallback": (0.0, 0.0)},
    )

    result = adapter.execute_window(
        task_actions=[{"task_id": "task-critical", "action": "RUN", "lane": "CRITICAL_LANE"}],
        now_ms=1001,
    )

    assert ensured == [["task-critical"]]
    assert resumed == ["task-critical"]
    assert stopped == []
    assert publisher.calls == [("motion", 0.6, 0.4)]
    assert result["cmd_vel"] == {"type": "motion", "vx": 0.6, "wz": 0.4}
