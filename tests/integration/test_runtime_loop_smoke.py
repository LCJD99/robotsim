from runtime_scheduler.main import run_once_for_test


def test_runtime_smoke_creates_all_trace_files(tmp_path):
    run_once_for_test(output_root=tmp_path)

    experiment_dirs = [path for path in tmp_path.iterdir() if path.is_dir()]
    assert len(experiment_dirs) == 1

    files = {path.name for path in experiment_dirs[0].iterdir()}
    assert files >= {
        "window_observation.jsonl",
        "plan.jsonl",
        "outcome.jsonl",
        "task_events.jsonl",
        "resource_samples.jsonl",
    }
