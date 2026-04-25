from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class NumericBounds:
    min_value: float
    max_value: float

    def contains(self, value: float) -> bool:
        return self.min_value <= value <= self.max_value


@dataclass(frozen=True, slots=True)
class NodeSpec:
    node_id: str
    cpu_quota: NumericBounds
    max_concurrency: NumericBounds


@dataclass(frozen=True, slots=True)
class EdgeSpec:
    edge_id: str


class RegistryClient(Protocol):
    def get_node_spec(self, node_id: str) -> NodeSpec: ...

    def get_edge_spec(self, edge_id: str) -> EdgeSpec: ...
