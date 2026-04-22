from __future__ import annotations


class CmdVelPublisher:
    def __init__(self, topic: str = "/cmd_vel", node_name: str = "runtime_scheduler_cmd_vel") -> None:
        try:
            import rclpy
            from geometry_msgs.msg import Twist
            from rclpy.node import Node
        except ImportError as exc:
            raise ImportError(
                "ROS 2 Python dependencies are required for CmdVelPublisher "
                "(rclpy, geometry_msgs)."
            ) from exc

        self._rclpy = rclpy
        self._twist_cls = Twist
        self._owns_rclpy_context = False
        if not self._rclpy.ok():
            self._rclpy.init(args=None)
            self._owns_rclpy_context = True

        self._node = Node(node_name)
        self._publisher = self._node.create_publisher(Twist, topic, 10)

    def publish_motion(self, vx: float, wz: float) -> None:
        msg = self._twist_cls()
        msg.linear.x = float(vx)
        msg.angular.z = float(wz)
        self._publisher.publish(msg)
        self._rclpy.spin_once(self._node, timeout_sec=0.0)

    def publish_stop(self) -> None:
        self.publish_motion(0.0, 0.0)

    def close(self) -> None:
        self._node.destroy_node()
        if self._owns_rclpy_context and self._rclpy.ok():
            self._rclpy.shutdown()
