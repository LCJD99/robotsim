from __future__ import annotations

import os
import signal
import subprocess
import sys
from collections.abc import Callable, Iterable


class WorkerManager:
    def __init__(
        self,
        spawn_fn: Callable[[str], int] | None = None,
        resume_fn: Callable[[int], bool] | None = None,
        stop_fn: Callable[[int], bool] | None = None,
        attach_fn: Callable[[int], None] | None = None,
    ) -> None:
        self._spawn_fn = spawn_fn or self._default_spawn
        self._resume_fn = resume_fn or self._default_resume
        self._stop_fn = stop_fn or self._default_stop
        self._attach_fn = attach_fn or self._default_attach
        self._task_pid_map: dict[str, int] = {}

    def ensure_workers(self, task_ids: Iterable[str]) -> None:
        for task_id in task_ids:
            if task_id in self._task_pid_map:
                continue
            pid = self._spawn_fn(task_id)
            self._attach_fn(pid)
            self._task_pid_map[task_id] = pid

    def get_pid(self, task_id: str) -> int | None:
        return self._task_pid_map.get(task_id)

    def resume_task(self, task_id: str) -> bool:
        pid = self.get_pid(task_id)
        if pid is None:
            return False
        return self._resume_fn(pid)

    def stop_task(self, task_id: str) -> bool:
        pid = self.get_pid(task_id)
        if pid is None:
            return False
        return self._stop_fn(pid)

    def _default_spawn(self, _task_id: str) -> int:
        process = subprocess.Popen(
            [sys.executable, "-m", "runtime_scheduler.worker_process"]
        )
        return process.pid

    def _default_resume(self, pid: int) -> bool:
        try:
            os.kill(pid, signal.SIGCONT)
            return True
        except OSError:
            return False

    def _default_stop(self, pid: int) -> bool:
        try:
            os.kill(pid, signal.SIGSTOP)
            return True
        except OSError:
            return False

    def _default_attach(self, _pid: int) -> None:
        return None
