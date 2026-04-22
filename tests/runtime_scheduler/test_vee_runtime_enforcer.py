from pathlib import Path

import pytest

from runtime_scheduler.vee_runtime_enforcer import VeeRuntimeEnforcer


class _Result:
    def __init__(self, returncode: int) -> None:
        self.returncode = returncode


def test_enforce_startup_raises_runtime_error_on_nonzero_return_code(monkeypatch, tmp_path):
    script_path = tmp_path / "apply_runtime_constraints.sh"
    script_path.write_text("#!/bin/sh\nexit 2\n", encoding="utf-8")

    def _fake_run(cmd, check):
        assert cmd == [str(script_path)]
        assert check is False
        return _Result(returncode=2)

    monkeypatch.setattr("runtime_scheduler.vee_runtime_enforcer.subprocess.run", _fake_run)

    enforcer = VeeRuntimeEnforcer(
        script_path=str(script_path),
        cgroup_procs_path=str(tmp_path / "cgroup.procs"),
    )

    with pytest.raises(RuntimeError, match="VEE startup enforcement failed"):
        enforcer.enforce_startup()


def test_attach_pid_writes_expected_content(tmp_path):
    cgroup_procs_path = tmp_path / "a" / "b" / "cgroup.procs"
    enforcer = VeeRuntimeEnforcer(
        script_path=str(tmp_path / "apply_runtime_constraints.sh"),
        cgroup_procs_path=str(cgroup_procs_path),
    )

    enforcer.attach_pid(12345)

    assert cgroup_procs_path.read_text(encoding="utf-8") == "12345\n"
