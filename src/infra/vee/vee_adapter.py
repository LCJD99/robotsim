from __future__ import annotations

from collections.abc import Mapping


class VeeAdapter:
    def __init__(self, profile: Mapping[str, object]):
        self._profile = profile

    def planned_commands(self) -> list[str]:
        cpu = self._profile["cpu"]
        memory = self._profile["memory"]

        if not isinstance(cpu, Mapping):
            raise TypeError("profile['cpu'] must be a mapping")
        if not isinstance(memory, Mapping):
            raise TypeError("profile['memory'] must be a mapping")

        return [
            f"echo {cpu['cpuset']} > /sys/fs/cgroup/vee/cpuset.cpus",
            f"echo {cpu['quota']} > /sys/fs/cgroup/vee/cpu.max",
            f"echo {memory['high']} > /sys/fs/cgroup/vee/memory.high",
            f"echo {memory['max']} > /sys/fs/cgroup/vee/memory.max",
            "hami-core apply --group vee",
        ]
