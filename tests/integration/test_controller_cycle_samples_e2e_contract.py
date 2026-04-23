from __future__ import annotations

import json

from runtime_scheduler.main import run_once_for_test


REQUIRED_KEYS = {
    "schema_version",
    "experiment_id",
    "window_id",
    "timestamp_us",
    "controller_name",
    "period_target_us",
    "cycle_count",
    "exec_mono_us_p50",
    "exec_mono_us_p95",
    "exec_mono_us_max",
    "period_sim_us_p50",
    "period_sim_us_p95",
    "period_sim_us_max",
    "deadline_miss_exec_count",
    "late_start_sim_count",
    "late_finish_sim_count",
    "late_arrival_count",
}


def test_run_once_outputs_controller_cycle_samples_file(tmp_path):
    run_once_for_test(output_root=tmp_path)

    experiment_dirs = [path for path in tmp_path.iterdir() if path.is_dir()]
    assert experiment_dirs
    latest_experiment_dir = max(experiment_dirs, key=lambda path: path.stat().st_mtime_ns)

    sample_file = latest_experiment_dir / "controller_cycle_samples.jsonl"
    assert sample_file.exists()

    rows = [json.loads(line) for line in sample_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(rows) == 2
    controller_names = {row["controller_name"] for row in rows}
    assert controller_names == {"joint_state_broadcaster", "diff_drive_controller"}

    for row in rows:
        assert REQUIRED_KEYS.issubset(row.keys())
        assert row["schema_version"] == "v1"
        assert row["window_id"] == "window-1"
        assert row["cycle_count"] >= 0
