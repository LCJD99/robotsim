from __future__ import annotations

from collections import deque
from collections.abc import Mapping
import json
import time


class TopicControllerCycleSource:
    """Collect controller cycle metrics records from a ROS topic and drain by window."""

    def __init__(
        self,
        topic: str = "/controller_cycle_metrics",
        node_name: str = "runtime_scheduler_controller_cycle_source",
    ) -> None:
        try:
            import rclpy
            from rclpy.node import Node
            from std_msgs.msg import String
        except ImportError as exc:
            raise ImportError(
                "ROS 2 Python dependencies are required for TopicControllerCycleSource "
                "(rclpy, std_msgs)."
            ) from exc

        self._rclpy = rclpy
        self._node_cls = Node
        self._string_cls = String
        self._owns_context = False
        if not self._rclpy.ok():
            self._rclpy.init(args=None)
            self._owns_context = True

        self._node = self._node_cls(node_name)
        self._queue: deque[dict[str, object]] = deque()
        self._subscription = self._node.create_subscription(
            self._string_cls,
            topic,
            self._on_message,
            100,
        )

    def _on_message(self, msg: object) -> None:
        try:
            payload = json.loads(str(msg.data))
        except Exception:
            return

        if not isinstance(payload, Mapping):
            return
        record = dict(payload)
        record["_arrival_mono_us"] = time.monotonic_ns() // 1_000
        self._queue.append(record)

    def drain_window(self, window_start_us: int, window_end_us: int) -> list[dict[str, object]]:
        for _ in range(8):
            self._rclpy.spin_once(self._node, timeout_sec=0.0)

        ready: list[dict[str, object]] = []
        retained: deque[dict[str, object]] = deque()

        while self._queue:
            record = self._queue.popleft()
            cycle_end_sim_us = int(record.get("cycle_end_sim_us", 0))
            if cycle_end_sim_us < window_start_us:
                record["late_arrival"] = True
                ready.append(record)
            elif cycle_end_sim_us < window_end_us:
                record["late_arrival"] = bool(record.get("late_arrival", False))
                ready.append(record)
            else:
                retained.append(record)

        self._queue = retained
        return ready

    def close(self) -> None:
        self._node.destroy_node()
        if self._owns_context and self._rclpy.ok():
            self._rclpy.shutdown()
