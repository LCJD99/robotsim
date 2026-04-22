from __future__ import annotations

from pathlib import Path
import subprocess


class VeeRuntimeEnforcer:
    def __init__(self, script_path: str, cgroup_procs_path: str) -> None:
        self._script_path = script_path
        self._cgroup_procs_path = Path(cgroup_procs_path)

    def enforce_startup(self) -> None:
        result = subprocess.run([self._script_path], check=False)
        if result.returncode != 0:
            raise RuntimeError(
                f"VEE startup enforcement failed with exit code {result.returncode}"
            )

    def attach_pid(self, pid: int) -> None:
        self._cgroup_procs_path.parent.mkdir(parents=True, exist_ok=True)
        with self._cgroup_procs_path.open("a", encoding="utf-8") as f:
            f.write(f"{pid}\n")
