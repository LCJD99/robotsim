from __future__ import annotations

MODES = ("NORMAL", "CONSERVATIVE", "DEGRADED", "EMERGENCY")


class HybridModeTrigger:
    def __init__(self, cooldown_windows: int):
        if cooldown_windows < 0:
            raise ValueError("cooldown_windows must be non-negative")
        self.cooldown_windows = int(cooldown_windows)
        self._last_raise_window = -(10**9)

    def decide(self, window_index: int, runtime_raise: bool, scheduler_requested: str) -> str:
        if runtime_raise:
            self._last_raise_window = int(window_index)
            return "CONSERVATIVE"

        if window_index - self._last_raise_window < self.cooldown_windows:
            return "CONSERVATIVE"

        if scheduler_requested in MODES:
            return scheduler_requested
        return "NORMAL"
