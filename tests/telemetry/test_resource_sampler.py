from telemetry.resource_sampler import make_resource_sample
from vee.vee_adapter import VeeAdapter


def test_resource_sample_has_required_top_level_keys():
    sample = make_resource_sample(
        experiment_id="20260421-120000",
        sample_id="s1",
        timestamp_us=1,
    )

    assert set(sample) >= {
        "schema_version",
        "experiment_id",
        "sample_id",
        "timestamp_us",
        "scope",
        "cpu",
        "memory",
        "gpu",
        "network",
    }


def test_vee_adapter_planned_commands_match_profile():
    adapter = VeeAdapter(
        {
            "cpu": {"cpuset": "0-1", "quota": "200000 100000"},
            "memory": {"high": "6G", "max": "8G"},
        }
    )

    assert adapter.planned_commands() == [
        "echo 0-1 > /sys/fs/cgroup/vee/cpuset.cpus",
        "echo 200000 100000 > /sys/fs/cgroup/vee/cpu.max",
        "echo 6G > /sys/fs/cgroup/vee/memory.high",
        "echo 8G > /sys/fs/cgroup/vee/memory.max",
    ]
