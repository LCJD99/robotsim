from __future__ import annotations

import json
from pathlib import Path

from runtime_scheduler.e2e_runner import E2ERunner


class FakeProcess:
    def __init__(self, kind: str, wait_code: int = 0) -> None:
        self.kind = kind
        self._wait_code = wait_code
        self.returncode: int | None = None
        self.terminate_called = False
        self.kill_called = False

    def poll(self) -> int | None:
        return self.returncode

    def wait(self) -> int:
        if self.returncode is None:
            self.returncode = self._wait_code
        return self.returncode

    def terminate(self) -> None:
        self.terminate_called = True
        if self.returncode is None:
            self.returncode = 0

    def kill(self) -> None:
        self.kill_called = True
        if self.returncode is None:
            self.returncode = -9


def test_e2e_runner_success_writes_summary_and_stops_sim(tmp_path: Path):
    created: list[FakeProcess] = []

    def popen_factory(command):
        kind = "sim" if command[0] == "sim" else "scheduler"
        wait_code = 0
        proc = FakeProcess(kind=kind, wait_code=wait_code)
        created.append(proc)
        return proc

    checks = iter([False, True])

    def readiness_check() -> bool:
        return next(checks)

    runner = E2ERunner(
        sim_command=["sim", "launch"],
        scheduler_command=["scheduler", "run"],
        summary_path=tmp_path / "run_summary.json",
        readiness_check=readiness_check,
        popen_factory=popen_factory,
        wait_ready_timeout_sec=5.0,
        poll_interval_sec=0.0,
    )

    summary = runner.run()

    assert summary["status"] == "success"
    assert summary["reason"] == "completed"
    assert summary["scheduler_exit_code"] == 0
    assert summary["sim_exit_code"] == 0
    assert created[0].terminate_called is True
    on_disk = json.loads((tmp_path / "run_summary.json").read_text(encoding="utf-8"))
    assert on_disk == summary


def test_e2e_runner_readiness_timeout(tmp_path: Path):
    def popen_factory(command):
        kind = "sim" if command[0] == "sim" else "scheduler"
        return FakeProcess(kind=kind, wait_code=0)

    now = [0.0]

    def monotonic_fn() -> float:
        return now[0]

    def sleep_fn(delay: float) -> None:
        now[0] += max(delay, 0.1)

    runner = E2ERunner(
        sim_command=["sim", "launch"],
        scheduler_command=["scheduler", "run"],
        summary_path=tmp_path / "run_summary.json",
        readiness_check=lambda: False,
        popen_factory=popen_factory,
        wait_ready_timeout_sec=0.25,
        poll_interval_sec=0.1,
        monotonic_fn=monotonic_fn,
        sleep_fn=sleep_fn,
    )

    summary = runner.run()

    assert summary["status"] == "failed"
    assert summary["reason"] == "readiness_timeout"
    assert summary["scheduler_exit_code"] is None
    assert summary["sim_exit_code"] == 0
