from __future__ import annotations

import math
import random
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class _ArrivalMetadata:
    event_type: str
    task_id: str
    request_id: str
    window_id: str
    timestamp_us: int
    arrival_source: str
    generator_seed: int
    lambda_per_sec: float


class PoissonLocalToolGenerator:
    def __init__(self, lambda_per_sec: float, window_ms: int, seed: int, max_arrivals_per_window: int):
        if window_ms <= 0:
            raise ValueError("window_ms must be positive")
        if max_arrivals_per_window < 0:
            raise ValueError("max_arrivals_per_window must be non-negative")
        if lambda_per_sec < 0:
            raise ValueError("lambda_per_sec must be non-negative")

        self.lambda_per_sec = float(lambda_per_sec)
        self.window_ms = int(window_ms)
        self.seed = int(seed)
        self.max_arrivals_per_window = int(max_arrivals_per_window)
        self._rng = random.Random(seed)
        self._sequence = 0

    def _sample_poisson(self, mean: float) -> int:
        if mean <= 0.0:
            return 0

        threshold = math.exp(-mean)
        count = 0
        product = 1.0
        while product > threshold:
            count += 1
            product *= self._rng.random()
        return count - 1

    def next_arrivals(self, window_id: str, timestamp_us: int) -> list[dict[str, object]]:
        mean = self.lambda_per_sec * (self.window_ms / 1000.0)
        arrival_count = min(self._sample_poisson(mean), self.max_arrivals_per_window)
        arrivals: list[dict[str, object]] = []

        for _ in range(arrival_count):
            self._sequence += 1
            metadata = _ArrivalMetadata(
                event_type="TASK_ARRIVAL",
                task_id=f"local-tool-{self._sequence}",
                request_id=f"request-{self._sequence}",
                window_id=window_id,
                timestamp_us=timestamp_us,
                arrival_source="poisson",
                generator_seed=self.seed,
                lambda_per_sec=self.lambda_per_sec,
            )
            arrivals.append(
                {
                    "event_type": metadata.event_type,
                    "task_id": metadata.task_id,
                    "request_id": metadata.request_id,
                    "window_id": metadata.window_id,
                    "timestamp_us": metadata.timestamp_us,
                    "arrival_source": metadata.arrival_source,
                    "generator_seed": metadata.generator_seed,
                    "lambda_per_sec": metadata.lambda_per_sec,
                }
            )

        return arrivals
