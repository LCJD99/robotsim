from runtime_scheduler.controller_cycle_aggregator import ControllerCycleAggregator


def test_aggregate_window_computes_expected_metrics():
    aggregator = ControllerCycleAggregator(
        controller_names=("joint_state_broadcaster", "diff_drive_controller"),
        period_target_us=20_000,
    )
    records = [
        {
            "controller_name": "joint_state_broadcaster",
            "period_target_us": 20_000,
            "exec_time_mono_us": 10_000,
            "cycle_period_sim_us": 20_100,
            "deadline_miss_exec": False,
            "late_start_sim": False,
            "late_finish_sim": False,
            "late_arrival": False,
        },
        {
            "controller_name": "joint_state_broadcaster",
            "period_target_us": 20_000,
            "exec_time_mono_us": 21_000,
            "cycle_period_sim_us": 20_400,
            "deadline_miss_exec": True,
            "late_start_sim": True,
            "late_finish_sim": False,
            "late_arrival": True,
        },
    ]

    samples = aggregator.aggregate_window(
        experiment_id="exp-1",
        window_id="window-1",
        timestamp_us=1_000_000,
        records=records,
    )

    by_controller = {sample["controller_name"]: sample for sample in samples}

    js = by_controller["joint_state_broadcaster"]
    assert js["cycle_count"] == 2
    assert js["exec_mono_us_p50"] == 10_000
    assert js["exec_mono_us_p95"] == 21_000
    assert js["exec_mono_us_max"] == 21_000
    assert js["period_sim_us_p50"] == 20_100
    assert js["period_sim_us_p95"] == 20_400
    assert js["period_sim_us_max"] == 20_400
    assert js["deadline_miss_exec_count"] == 1
    assert js["late_start_sim_count"] == 1
    assert js["late_finish_sim_count"] == 0
    assert js["late_arrival_count"] == 1

    dd = by_controller["diff_drive_controller"]
    assert dd["cycle_count"] == 0
    assert dd["period_target_us"] == 20_000
    assert dd["exec_mono_us_p50"] == 0
    assert dd["period_sim_us_p50"] == 0
    assert dd["deadline_miss_exec_count"] == 0
