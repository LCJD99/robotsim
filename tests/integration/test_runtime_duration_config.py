from pathlib import Path

from runtime_scheduler.config import load_config


def test_default_config_has_120s_and_50ms():
    cfg = load_config(Path("experiment_configs/v1_dynamic_dense.yaml"))

    assert cfg.experiment.duration_sec == 120
    assert cfg.scheduler.window_ms == 50
