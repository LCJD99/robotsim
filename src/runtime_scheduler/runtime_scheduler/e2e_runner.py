from __future__ import annotations

from collections.abc import Callable, Sequence
import json
from pathlib import Path
import subprocess
import time


class E2ERunner:
    """Orchestrate sim-launch and scheduler processes with a testable contract."""

    def __init__(
        self,
        *,
        sim_command: Sequence[str],
        scheduler_command: Sequence[str],
        summary_path: Path | str,
        readiness_check: Callable[[], bool],
        popen_factory: Callable[..., object] = subprocess.Popen,
        wait_ready_timeout_sec: float = 30.0,
        poll_interval_sec: float = 0.2,
        terminate_timeout_sec: float = 5.0,
        monotonic_fn: Callable[[], float] = time.monotonic,
        sleep_fn: Callable[[float], None] = time.sleep,
    ) -> None:
        self._sim_command = list(sim_command)
        self._scheduler_command = list(scheduler_command)
        self._summary_path = Path(summary_path)
        self._readiness_check = readiness_check
        self._popen_factory = popen_factory
        self._wait_ready_timeout_sec = float(wait_ready_timeout_sec)
        self._poll_interval_sec = float(poll_interval_sec)
        self._terminate_timeout_sec = float(terminate_timeout_sec)
        self._monotonic_fn = monotonic_fn
        self._sleep_fn = sleep_fn

    def run(self) -> dict[str, object]:
        start_mono = self._monotonic_fn()
        sim_proc = None
        scheduler_proc = None
        summary: dict[str, object] = {
            "status": "failed",
            "reason": "unknown",
            "sim_exit_code": None,
            "scheduler_exit_code": None,
            "duration_sec": 0.0,
        }

        try:
            sim_proc = self._popen_factory(self._sim_command)
            ready_deadline = self._monotonic_fn() + self._wait_ready_timeout_sec
            while self._monotonic_fn() < ready_deadline:
                if sim_proc.poll() is not None:
                    summary["reason"] = "sim_launch_exited_before_ready"
                    summary["sim_exit_code"] = sim_proc.returncode
                    return self._finalize(summary, start_mono, sim_proc, scheduler_proc)
                if self._readiness_check():
                    break
                self._sleep_fn(self._poll_interval_sec)
            else:
                summary["reason"] = "readiness_timeout"
                return self._finalize(summary, start_mono, sim_proc, scheduler_proc)

            scheduler_proc = self._popen_factory(self._scheduler_command)
            scheduler_exit = scheduler_proc.wait()
            summary["scheduler_exit_code"] = scheduler_exit
            summary["sim_exit_code"] = sim_proc.poll()
            if scheduler_exit == 0:
                summary["status"] = "success"
                summary["reason"] = "completed"
            else:
                summary["reason"] = "scheduler_failed"

            return self._finalize(summary, start_mono, sim_proc, scheduler_proc)
        except Exception as exc:  # pragma: no cover - defensive path
            summary["reason"] = f"runner_exception:{type(exc).__name__}"
            return self._finalize(summary, start_mono, sim_proc, scheduler_proc)

    def _graceful_shutdown(self, proc: object | None) -> None:
        if proc is None:
            return
        if proc.poll() is not None:
            return

        proc.terminate()
        deadline = self._monotonic_fn() + self._terminate_timeout_sec
        while self._monotonic_fn() < deadline:
            if proc.poll() is not None:
                return
            self._sleep_fn(min(0.1, self._terminate_timeout_sec))

        if proc.poll() is None:
            proc.kill()

    def _finalize(
        self,
        summary: dict[str, object],
        start_mono: float,
        sim_proc: object | None,
        scheduler_proc: object | None,
    ) -> dict[str, object]:
        self._graceful_shutdown(scheduler_proc)
        self._graceful_shutdown(sim_proc)

        if scheduler_proc is not None:
            summary["scheduler_exit_code"] = scheduler_proc.poll()
        if sim_proc is not None:
            summary["sim_exit_code"] = sim_proc.poll()

        summary["duration_sec"] = max(0.0, self._monotonic_fn() - start_mono)
        self._summary_path.parent.mkdir(parents=True, exist_ok=True)
        self._summary_path.write_text(json.dumps(summary, ensure_ascii=True), encoding="utf-8")
        return summary


def default_readiness_check() -> bool:
    """Hook for production integration; tests should inject deterministic readiness."""

    return False
