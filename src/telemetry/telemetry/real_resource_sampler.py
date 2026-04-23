from __future__ import annotations

import subprocess
import time
from pathlib import Path


class RealResourceSampler:
    """Reads real resource metrics with per-source graceful fallback."""

    def __init__(
        self,
        cgroup_root: str = "/sys/fs/cgroup/vee",
        sample_interval_ms: int = 50,
    ) -> None:
        self._cgroup = Path(cgroup_root)
        self._sample_interval_ms = sample_interval_ms
        self._prev_cpu_usage_usec = 0
        self._prev_cpu_wall_s = time.monotonic()
        self._prev_net_tx_bytes = 0
        self._prev_net_rx_bytes = 0
        self._prev_net_wall_s = time.monotonic()

    def sample(self) -> dict[str, object]:
        return {
            "schema_version": "v1",
            "scope": "system",
            "cpu": {"utilization_total": self._cpu_utilization()},
            "memory": self._memory(),
            "gpu": self._gpu(),
            "network": self._network(),
        }

    def _cpu_utilization(self) -> float:
        try:
            usage_usec = self._read_cpu_usage_usec(self._cgroup / "cpu.stat")
        except Exception:
            return 0.0

        now = time.monotonic()
        delta_usec = max(0, usage_usec - self._prev_cpu_usage_usec)
        delta_wall_s = now - self._prev_cpu_wall_s
        self._prev_cpu_usage_usec = usage_usec
        self._prev_cpu_wall_s = now

        if delta_wall_s <= 0:
            return 0.0
        return min(delta_usec / (delta_wall_s * 1_000_000), 1.0)

    @staticmethod
    def _read_cpu_usage_usec(path: Path) -> int:
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("usage_usec"):
                return int(line.split()[1])
        raise ValueError(f"usage_usec not found in {path}")

    def _memory(self) -> dict[str, int]:
        try:
            used_bytes = int((self._cgroup / "memory.current").read_text(encoding="utf-8").strip())
            max_raw = (self._cgroup / "memory.max").read_text(encoding="utf-8").strip()
            max_bytes = int(max_raw) if max_raw != "max" else 0
            available_bytes = max(max_bytes - used_bytes, 0) if max_bytes > 0 else 0
            return {"used_bytes": used_bytes, "available_bytes": available_bytes}
        except Exception:
            return {"used_bytes": 0, "available_bytes": 0}

    def _gpu(self) -> dict[str, object]:
        try:
            result = subprocess.run(
                [
                    "nvidia-smi",
                    "--query-gpu=utilization.gpu,memory.used",
                    "--format=csv,noheader,nounits",
                ],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if result.returncode != 0:
                return {"utilization": 0.0, "memory_used_bytes": 0}
            util_text, mem_text = [part.strip() for part in result.stdout.strip().split(",", maxsplit=1)]
            util_pct = float(util_text)
            mem_mib = float(mem_text)
            return {
                "utilization": round(util_pct / 100.0, 4),
                "memory_used_bytes": int(mem_mib * 1024 * 1024),
            }
        except Exception:
            return {"utilization": 0.0, "memory_used_bytes": 0}

    def _network(self) -> dict[str, int]:
        try:
            tx_bytes, rx_bytes = self._read_net_bytes()
        except Exception:
            return {"tx_rate_bps": 0, "rx_rate_bps": 0}

        now = time.monotonic()
        delta_s = now - self._prev_net_wall_s
        delta_tx = max(0, tx_bytes - self._prev_net_tx_bytes)
        delta_rx = max(0, rx_bytes - self._prev_net_rx_bytes)
        self._prev_net_tx_bytes = tx_bytes
        self._prev_net_rx_bytes = rx_bytes
        self._prev_net_wall_s = now

        if delta_s <= 0:
            return {"tx_rate_bps": 0, "rx_rate_bps": 0}
        return {
            "tx_rate_bps": int((delta_tx * 8) / delta_s),
            "rx_rate_bps": int((delta_rx * 8) / delta_s),
        }

    @staticmethod
    def _read_net_bytes() -> tuple[int, int]:
        total_tx = 0
        total_rx = 0
        for line in Path("/proc/net/dev").read_text(encoding="utf-8").splitlines()[2:]:
            parts = line.split()
            if len(parts) < 10:
                continue
            if parts[0].rstrip(":") == "lo":
                continue
            total_rx += int(parts[1])
            total_tx += int(parts[9])
        return total_tx, total_rx
