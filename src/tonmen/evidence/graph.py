from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class GraphNode:
    id: str
    kind: str
    label: str
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class GraphEdge:
    source: str
    relation: str
    target: str


class EvidenceGraph:
    """Small in-memory provenance graph for missions, observations and evidence."""

    def __init__(self) -> None:
        self.nodes: dict[str, GraphNode] = {}
        self.edges: list[GraphEdge] = []

    def add_node(self, node: GraphNode) -> None:
        self.nodes[node.id] = node

    def link(self, source: str, relation: str, target: str) -> None:
        if source not in self.nodes or target not in self.nodes:
            raise KeyError("both graph nodes must exist before linking")
        self.edges.append(GraphEdge(source=source, relation=relation, target=target))
