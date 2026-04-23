from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from telemetry.real_resource_sampler import RealResourceSampler


def _write_cgroup_files(root: Path, cpu_usage_usec: int, mem_current: int, mem_max: int) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "cpu.stat").write_text(f"usage_usec {cpu_usage_usec}\n", encoding="utf-8")
    (root / "memory.current").write_text(f"{mem_current}\n", encoding="utf-8")
    (root / "memory.max").write_text(f"{mem_max}\n", encoding="utf-8")


def test_sample_returns_required_schema_keys(tmp_path):
    _write_cgroup_files(tmp_path, 0, 0, 1)
    s = RealResourceSampler(cgroup_root=str(tmp_path), sample_interval_ms=50)
    result = s.sample()
    assert set(result) >= {"schema_version", "cpu", "memory", "gpu", "network", "scope"}
    assert result["schema_version"] == "v1"
    assert result["scope"] == "system"


def test_cpu_utilization_computed_from_delta(tmp_path):
    _write_cgroup_files(tmp_path, 0, 0, 1)
    s = RealResourceSampler(cgroup_root=str(tmp_path), sample_interval_ms=50)
    s.sample()
    s._prev_cpu_usage_usec = 0
    s._prev_cpu_wall_s = 0.0

    _write_cgroup_files(tmp_path, 25_000, 0, 1)
    with patch("time.monotonic", side_effect=[0.05, 0.05]):
        result = s.sample()

    cpu = result["cpu"]["utilization_total"]
    assert cpu == pytest.approx(0.5, rel=1e-3)


def test_memory_reads_current_and_max(tmp_path):
    _write_cgroup_files(tmp_path, 0, 4_000_000, 8_000_000)
    s = RealResourceSampler(cgroup_root=str(tmp_path), sample_interval_ms=50)
    result = s.sample()
    assert result["memory"]["used_bytes"] == 4_000_000
    assert result["memory"]["available_bytes"] == 4_000_000


def test_gpu_parsed_from_nvidia_smi(tmp_path):
    _write_cgroup_files(tmp_path, 0, 0, 1)
    s = RealResourceSampler(cgroup_root=str(tmp_path), sample_interval_ms=50)

    class _R:
        returncode = 0
        stdout = "42, 1024\n"

    with patch("subprocess.run", return_value=_R()):
        result = s.sample()

    assert result["gpu"]["utilization"] == pytest.approx(0.42)
    assert result["gpu"]["memory_used_bytes"] == 1024 * 1024 * 1024


def test_all_metrics_fallback_to_zero_when_cgroup_absent(tmp_path):
    missing = tmp_path / "nonexistent"
    s = RealResourceSampler(cgroup_root=str(missing), sample_interval_ms=50)

    with patch("subprocess.run", side_effect=FileNotFoundError):
        result = s.sample()

    assert result["cpu"]["utilization_total"] == 0.0
    assert result["memory"]["used_bytes"] == 0
    assert result["gpu"]["utilization"] == 0.0
    assert result["network"]["tx_rate_bps"] == 0
