from runtime_scheduler.workload_generator import PoissonLocalToolGenerator


def test_poisson_generator_is_seed_deterministic():
    generator_a = PoissonLocalToolGenerator(
        lambda_per_sec=4.0,
        window_ms=50,
        seed=42,
        max_arrivals_per_window=8,
    )
    generator_b = PoissonLocalToolGenerator(
        lambda_per_sec=4.0,
        window_ms=50,
        seed=42,
        max_arrivals_per_window=8,
    )

    assert generator_a.next_arrivals(window_id="w1", timestamp_us=1000) == generator_b.next_arrivals(
        window_id="w1",
        timestamp_us=1000,
    )


def test_poisson_generator_respects_per_window_cap(monkeypatch):
    generator = PoissonLocalToolGenerator(
        lambda_per_sec=200.0,
        window_ms=50,
        seed=42,
        max_arrivals_per_window=3,
    )
    monkeypatch.setattr(generator, "_sample_poisson", lambda mean: 10)

    arrivals = generator.next_arrivals(window_id="w1", timestamp_us=1)

    assert len(arrivals) == 3
    assert all(arrival["arrival_source"] == "poisson" for arrival in arrivals)
