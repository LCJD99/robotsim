from __future__ import annotations


def make_resource_sample(experiment_id: str, sample_id: str, timestamp_us: int) -> dict[str, object]:
    return {
        "schema_version": "v1",
        "experiment_id": experiment_id,
        "sample_id": sample_id,
        "timestamp_us": timestamp_us,
        "window_id": None,
        "scope": "system",
        "cpu": {"utilization_total": 0.0},
        "memory": {"used_bytes": 0, "available_bytes": 0},
        "gpu": {"utilization": 0.0, "memory_used_bytes": 0},
        "network": {"tx_rate_bps": 0, "rx_rate_bps": 0},
    }
