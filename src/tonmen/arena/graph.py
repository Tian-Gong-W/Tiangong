from __future__ import annotations

import copy
import math
from typing import Any, Dict, List, Optional, Set, Tuple
import networkx as nx

from .models import LootCategory, LootItem, NodeType


class ProbabilisticAttackGraph:
    """Probabilistic Attack Graph (PAG) with AND/OR nodes.

    Calculates the exact marginal progress contribution Delta P towards the goal:
      P(Goal | Graph)
      Delta P = P(Goal | Graph + Loot) - P(Goal | Graph)
    """

    def __init__(self, goal_node_id: str = "goal_objective") -> None:
        self.graph = nx.DiGraph()
        self.goal_node_id = goal_node_id
        self.achieved_nodes: Set[str] = set()
        self.loot_history: List[LootItem] = []

        # Add initial goal node
        self.graph.add_node(
            self.goal_node_id,
            node_type=NodeType.OR_NODE,
            title="Goal Objective",
            achieved=False,
            base_prob=0.0,
        )

    def add_state_node(
        self,
        node_id: str,
        title: str,
        node_type: NodeType = NodeType.OR_NODE,
        achieved: bool = False,
    ) -> None:
        self.graph.add_node(
            node_id,
            node_type=node_type,
            title=title,
            achieved=achieved,
        )
        if achieved:
            self.achieved_nodes.add(node_id)

    def add_transition(
        self,
        from_node: str,
        to_node: str,
        success_prob: float = 0.8,
        detection_risk: float = 1.0,
        cost: float = 1.0,
        label: str = "",
    ) -> None:
        if from_node not in self.graph:
            self.add_state_node(from_node, from_node)
        if to_node not in self.graph:
            self.add_state_node(to_node, to_node)
        self.graph.add_edge(
            from_node,
            to_node,
            success_prob=min(1.0, max(0.01, success_prob)),
            detection_risk=detection_risk,
            cost=cost,
            label=label,
        )

    def calculate_goal_probability(self) -> float:
        """Calculates P(Goal | Graph) using topological dynamic programming."""
        if not nx.is_directed_acyclic_graph(self.graph):
            # Fallback if cycles exist: break cycles by greedy DFS edge removal
            dag = self._to_dag(self.graph)
        else:
            dag = self.graph

        if self.goal_node_id not in dag:
            return 0.0

        probs: Dict[str, float] = {}

        try:
            topo_order = list(nx.topological_sort(dag))
        except nx.NetworkXUnfeasible:
            return 0.0

        for node in topo_order:
            node_data = dag.nodes[node]
            node_type = node_data.get("node_type", NodeType.OR_NODE)
            is_achieved = node in self.achieved_nodes or node_data.get("achieved", False)

            if is_achieved:
                probs[node] = 1.0
                continue

            preds = list(dag.predecessors(node))
            if not preds:
                probs[node] = 0.0
                continue

            if node_type == NodeType.AND_NODE:
                # AND node: All conditions must be met
                p_and = 1.0
                for pred in preds:
                    edge_prob = dag.edges[pred, node].get("success_prob", 0.8)
                    p_and *= (probs.get(pred, 0.0) * edge_prob)
                probs[node] = min(1.0, max(0.0, p_and))
            else:
                # OR node: Any path unlocks
                # P(node) = 1 - Prod(1 - P(pred) * p(edge))
                p_fail = 1.0
                for pred in preds:
                    edge_prob = dag.edges[pred, node].get("success_prob", 0.8)
                    p_path = probs.get(pred, 0.0) * edge_prob
                    p_fail *= (1.0 - p_path)
                probs[node] = min(1.0, max(0.0, 1.0 - p_fail))

        return probs.get(self.goal_node_id, 0.0)

    def calculate_marginal_progress(
        self,
        unlocked_nodes: List[str],
        loot: Optional[LootItem] = None,
    ) -> float:
        """Delta P = P(Goal | Graph + Loot) - P(Goal | Graph)."""
        current_p = self.calculate_goal_probability()

        # Simulate unlocking nodes
        original_achieved = set(self.achieved_nodes)
        for nid in unlocked_nodes:
            if nid in self.graph:
                self.achieved_nodes.add(nid)

        simulated_p = self.calculate_goal_probability()

        # Restore
        self.achieved_nodes = original_achieved

        delta_p = max(0.0, simulated_p - current_p)
        return delta_p

    def commit_loot(self, loot: LootItem, unlocked_nodes: List[str]) -> float:
        """Commits verified loot to graph and returns the actual marginal Delta P."""
        delta_p = self.calculate_marginal_progress(unlocked_nodes, loot)
        for nid in unlocked_nodes:
            if nid in self.graph:
                self.achieved_nodes.add(nid)
                self.graph.nodes[nid]["achieved"] = True
        self.loot_history.append(loot)
        return delta_p

    def snapshot(self) -> Dict[str, Any]:
        """Read-only snapshot of current graph for Strategist observation."""
        nodes = []
        for n, d in self.graph.nodes(data=True):
            nodes.append({
                "id": n,
                "title": d.get("title", n),
                "type": str(d.get("node_type", NodeType.OR_NODE)),
                "achieved": n in self.achieved_nodes,
            })
        edges = []
        for u, v, d in self.graph.edges(data=True):
            edges.append({
                "source": u,
                "target": v,
                "prob": d.get("success_prob", 0.8),
                "label": d.get("label", ""),
            })
        return {
            "nodes": nodes,
            "edges": edges,
            "achieved_count": len(self.achieved_nodes),
            "goal_prob": round(self.calculate_goal_probability(), 4),
            "loot_count": len(self.loot_history),
        }

    @staticmethod
    def _to_dag(graph: nx.DiGraph) -> nx.DiGraph:
        dag = graph.copy()
        while not nx.is_directed_acyclic_graph(dag):
            try:
                cycle = nx.find_cycle(dag, orientation="original")
                dag.remove_edge(cycle[0][0], cycle[0][1])
            except nx.NetworkXNoCycle:
                break
        return dag
