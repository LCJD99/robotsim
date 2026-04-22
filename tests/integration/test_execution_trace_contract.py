import json

from runtime_scheduler.main import run_once_for_test


def test_outcome_includes_execution_contract(tmp_path):
    run_once_for_test(output_root=tmp_path)

    experiment_dirs = [path for path in tmp_path.iterdir() if path.is_dir()]
    assert experiment_dirs
    latest_experiment_dir = max(experiment_dirs, key=lambda path: path.stat().st_mtime_ns)

    outcome_file = latest_experiment_dir / "outcome.jsonl"
    first_record = outcome_file.read_text(encoding="utf-8").splitlines()[0]
    outcome = json.loads(first_record)

    assert "execution" in outcome
    execution = outcome["execution"]
    assert "cmd_vel" in execution
    assert "worker_ops" in execution
