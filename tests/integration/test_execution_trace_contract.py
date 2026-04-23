import json

from runtime_scheduler.config import Config, TraceConfig, load_config
from runtime_scheduler.main import run_once_for_test
from runtime_scheduler.task_catalog import CONTROLLER_TASK_IDS


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

    plan_file = latest_experiment_dir / "plan.jsonl"
    first_plan = json.loads(plan_file.read_text(encoding="utf-8").splitlines()[0])
    task_actions = {action["task_id"]: action for action in first_plan["task_actions"]}
    for task_id in CONTROLLER_TASK_IDS:
        assert task_id in task_actions
        assert task_actions[task_id]["lane"] == "CRITICAL_LANE"

    task_events_file = latest_experiment_dir / "task_events.jsonl"
    task_events = [
        json.loads(line)
        for line in task_events_file.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    controller_events = [event for event in task_events if event["task_type"] == "ROS_CONTROLLER_CYCLE"]
    assert len(controller_events) == len(CONTROLLER_TASK_IDS)
    for event in controller_events:
        assert event["source"] == "controller_runtime"
        assert event["event_type"] == "TASK_ARRIVAL"
        assert event["arrival_source"] == "periodic_controller"
        assert event["generator_seed"] == -1
        assert event["lambda_per_sec"] == 0.0


def test_main_fallback_outcome_includes_offline_execution_marker(tmp_path, monkeypatch):
    from runtime_scheduler import main as main_module

    cfg = load_config("experiment_configs/v1_dynamic_dense.yaml")
    cfg = Config(
        experiment=cfg.experiment,
        scenario=cfg.scenario,
        scheduler=cfg.scheduler,
        trigger=cfg.trigger,
        agent=cfg.agent,
        agent_workload=cfg.agent_workload,
        execution=cfg.execution,
        sim=cfg.sim,
        vee=cfg.vee,
        trace=TraceConfig(root_dir=tmp_path),
    )
    monkeypatch.setattr(main_module, "load_config", lambda _path: cfg)
    monkeypatch.setattr(
        main_module,
        "run_stepped_experiment",
        lambda output_root, config: (_ for _ in ()).throw(ImportError("missing gz transport")),
    )

    main_module.main()

    experiment_dirs = [path for path in tmp_path.iterdir() if path.is_dir()]
    assert experiment_dirs
    latest_experiment_dir = max(experiment_dirs, key=lambda path: path.stat().st_mtime_ns)

    outcome_file = latest_experiment_dir / "outcome.jsonl"
    first_record = outcome_file.read_text(encoding="utf-8").splitlines()[0]
    outcome = json.loads(first_record)
    assert outcome["execution"] == {
        "mode": "offline_fallback",
        "success": False,
        "reason": "gz_transport_unavailable",
    }

    plan_file = latest_experiment_dir / "plan.jsonl"
    first_plan = json.loads(plan_file.read_text(encoding="utf-8").splitlines()[0])
    task_actions = {action["task_id"]: action for action in first_plan["task_actions"]}
    for task_id in CONTROLLER_TASK_IDS:
        assert task_id in task_actions
        assert task_actions[task_id]["lane"] == "CRITICAL_LANE"

    task_events_file = latest_experiment_dir / "task_events.jsonl"
    first_window_events = [
        json.loads(line)
        for line in task_events_file.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    first_window_controller_events = [
        event
        for event in first_window_events
        if event["window_id"] == "window-1" and event["task_type"] == "ROS_CONTROLLER_CYCLE"
    ]
    assert len(first_window_controller_events) == len(CONTROLLER_TASK_IDS)
