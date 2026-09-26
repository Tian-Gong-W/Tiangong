from __future__ import annotations

import math
import time
from typing import Any, Dict, List, Optional, Tuple

from .graph import ProbabilisticAttackGraph
from .ledger import ArenaLedger
from .models import (
    CircuitBreakerState,
    LeadHandoverEvent,
    LootCategory,
    LootItem,
    ProposalEvaluation,
    SubagentLootEvent,
    TacticalCombatResult,
    TacticalProposal,
)


class TheArbiter:
    """The central Arbiter referee engine.

    Evaluates Strategist proposals across the 3 fundamental dimensions:
      1. Theoretical Accuracy ("想得对不对")
      2. Execution Success Rate ("做得好不好")
      3. Risk / Reward Ratio ("划不划算" - powered by Marginal Progress Delta P)
    Decides Lead Strategist, arbitrates subagent looting, and triggers circuit breakers.
    """

    def __init__(
        self,
        graph: Optional[ProbabilisticAttackGraph] = None,
        ledger: Optional[ArenaLedger] = None,
        circuit_low_score_threshold: float = 25.0,
        circuit_consecutive_rounds: int = 3,
    ) -> None:
        self.graph = graph or ProbabilisticAttackGraph()
        self.ledger = ledger or ArenaLedger()
        self.current_round: int = 0
        self.circuit_state: CircuitBreakerState = CircuitBreakerState.NORMAL
        self.circuit_low_score_threshold = circuit_low_score_threshold
        self.circuit_consecutive_rounds = circuit_consecutive_rounds
        self.low_score_streak: int = 0
        self.event_log: List[Dict[str, Any]] = []

    def register_strategist(self, strategist_id: str, name: str, model: str) -> None:
        self.ledger.register_strategist(strategist_id, name, model)

    def evaluate_round(
        self,
        proposals: List[TacticalProposal],
        execution_results: Dict[str, Dict[str, Any]],
        phase_weights: Optional[Tuple[float, float, float]] = None,
    ) -> Dict[str, Any]:
        """Conducts a complete round evaluation:

        1. Prior Theoretical Accuracy check
        2. Posterior Execution Success check
        3. Marginal Progress Delta P calculation on graph
        4. Composite scoring & command shift / looting arbitration
        """
        self.current_round += 1
        w_theory, w_exec, w_rr = phase_weights or (0.3, 0.3, 0.4)

        round_scores: Dict[str, Dict[str, float]] = {}
        evaluations: List[ProposalEvaluation] = []

        for prop in proposals:
            s_id = prop.strategist_id
            exec_res = execution_results.get(prop.proposal_id, {})

            # 1. Theoretical Accuracy (0 - 100)
            # Checks if preconditions exist in graph and if logic matches topology
            accuracy = self._compute_theoretical_accuracy(prop)

            # 2. Execution Success Rate (0 - 100)
            # Checks ratio of successful actions vs failures/errors
            success_rate = self._compute_execution_success(prop, exec_res)

            # 3. Risk / Reward Ratio & Marginal Delta P
            # Powered by Graph marginal contribution
            unlocked_nodes = exec_res.get("unlocked_nodes", [])
            delta_p = 0.0
            if unlocked_nodes and success_rate > 50.0:
                loot = LootItem(
                    id=f"loot-{self.current_round}-{s_id}",
                    title=f"Loot from {prop.hypothesis[:30]}",
                    category=exec_res.get("loot_category", LootCategory.INFO),
                    confidence=success_rate / 100.0,
                    discovered_by=s_id,
                )
                delta_p = self.graph.commit_loot(loot, unlocked_nodes)

            # Risk reward formula: Delta P amplified, penalizing detection risk & cost
            risk_penalty = prop.risk_level * 5.0
            cost_penalty = prop.estimated_cost * 2.0
            base_reward = (delta_p * 100.0) + (10.0 if success_rate >= 80.0 else 0.0)
            risk_reward = max(5.0, min(100.0, base_reward - risk_penalty - cost_penalty + 50.0))

            # Composite Score
            composite = (
                w_theory * accuracy
                + w_exec * success_rate
                + w_rr * risk_reward
            )

            evaluations.append(
                ProposalEvaluation(
                    proposal_id=prop.proposal_id,
                    strategist_id=s_id,
                    theoretical_accuracy=round(accuracy, 1),
                    execution_success_rate=round(success_rate, 1),
                    risk_reward_ratio=round(risk_reward, 1),
                    marginal_delta_p=round(delta_p, 4),
                    composite_score=round(composite, 1),
                    rationale=f"Acc: {accuracy:.0f}%, Exec: {success_rate:.0f}%, ΔP: {delta_p*100:.1f}%",
                )
            )

            round_scores[s_id] = {
                "composite_score": composite,
                "accuracy": accuracy,
                "success_rate": success_rate,
                "risk_reward": risk_reward,
                "delta_p": delta_p,
            }

        # Settle in ledger (Command Shift & Looting)
        handover, loot = self.ledger.record_round_scores(self.current_round, round_scores)

        # Circuit Breaker Check
        avg_score = sum(s["composite_score"] for s in round_scores.values()) / max(1, len(round_scores))
        if avg_score < self.circuit_low_score_threshold:
            self.low_score_streak += 1
            if self.low_score_streak >= self.circuit_consecutive_rounds:
                self.circuit_state = CircuitBreakerState.STEALTH
        else:
            self.low_score_streak = 0
            if self.circuit_state == CircuitBreakerState.STEALTH:
                self.circuit_state = CircuitBreakerState.NORMAL

        event_summary = {
            "round": self.current_round,
            "goal_prob": round(self.graph.calculate_goal_probability(), 4),
            "leader": self.ledger.current_leader_id,
            "handover": handover.reason if handover else None,
            "loot": f"{loot.winner_id} looted {loot.loser_id}" if loot else None,
            "circuit_state": self.circuit_state.value,
            "evaluations": [
                {
                    "strategist_id": e.strategist_id,
                    "composite": e.composite_score,
                    "accuracy": e.theoretical_accuracy,
                    "success_rate": e.execution_success_rate,
                    "risk_reward": e.risk_reward_ratio,
                    "delta_p": e.marginal_delta_p,
                }
                for e in evaluations
            ],
        }
        self.event_log.append(event_summary)
        return event_summary

    def _compute_theoretical_accuracy(self, prop: TacticalProposal) -> float:
        """Evaluates logical consistency of preconditions and attack hypothesis."""
        if not prop.preconditions:
            return 85.0

        graph_nodes = set(self.graph.graph.nodes)
        matched = 0
        for prec in prop.preconditions:
            if prec in graph_nodes or prec in self.graph.achieved_nodes:
                matched += 1

        match_ratio = matched / len(prop.preconditions)
        # Score between 50 and 100 based on verified preconditions
        return min(100.0, 50.0 + (match_ratio * 50.0))

    def _compute_execution_success(
        self,
        prop: TacticalProposal,
        exec_res: Dict[str, Any],
    ) -> float:
        """Evaluates actual conversion of proposed actions."""
        if not exec_res:
            return 60.0

        total_actions = max(1, len(prop.proposed_actions))
        successful_actions = exec_res.get("successful_actions_count", 0)
        has_error = bool(exec_res.get("error"))

        ratio = (successful_actions / total_actions) * 100.0
        if has_error:
            ratio = max(10.0, ratio - 30.0)
        return min(100.0, max(0.0, ratio))

    def execute_tactical_combat(
        self,
        strategist_id: str,
        target_node: str,
        knowledge_hub: Optional[Any] = None,
        cost_points: int = 50,
        bounty_reward: int = 120,
    ) -> TacticalCombatResult:
        """Strategist manually enters tactical close-quarters combat against a high-value node.

        Consumes points, retrieves high-fidelity bypass/exploit intelligence from
        LiveSecurityKnowledgeHub, executes the offensive action, unlocks the node on the
        Probabilistic Attack Graph, computes marginal progress Delta P, and awards bounty points.
        """
        import uuid
        combat_id = f"combat-{uuid.uuid4().hex[:8]}"
        action_log: List[str] = []

        if not self.ledger.can_afford(strategist_id, cost_points):
            return TacticalCombatResult(
                combat_id=combat_id,
                round_number=self.current_round,
                strategist_id=strategist_id,
                target_node=target_node,
                points_cost=cost_points,
                success=False,
                reward_points=0,
                delta_p=0.0,
                action_log=[f"战略家 {strategist_id} 积分不足 (需要 {cost_points} 分，当前不可用)"],
                lead_captured=False,
            )

        # 1. Deduct cost points
        self.ledger.spend_points(strategist_id, cost_points)
        action_log.append(f"消耗 {cost_points} 竞技场积分，战略家 {strategist_id} 正式下场进入战术肉搏模式。")

        # 2. Query Live Security Knowledge Hub
        knowledge_refs = []
        if knowledge_hub:
            query = f"{target_node} bypass exploit 漏洞 绕过"
            docs = knowledge_hub.search(query, top_k=3)
            for d in docs:
                knowledge_refs.append(f"[{d.get('id', 'TKO')}] {d.get('title', '')}")
            if not knowledge_refs:
                knowledge_refs.append("[TKO-HEURISTIC] 深度特权突防与权限提升战术")
            action_log.append(f"从实时安全知识库中检索到 {len(knowledge_refs)} 条现代 TKO 绕过与利用情报。")
        else:
            knowledge_refs = ["[TKO-0DAY-2024] HTTP/2 Smuggling & JWT Algorithm Confusion Bypass"]
            action_log.append("从本地战术知识库中加载特权突防启发式规则。")

        # 3. Simulate or execute targeted breakthrough
        action_log.append(f"锁定核心防御节点 [{target_node}]，发起定向高侵略性武器化突防...")
        loot = LootItem(
            id=f"loot-tactical-{combat_id}",
            title=f"Tactical Combat Capture of {target_node}",
            category=LootCategory.ADMIN if "admin" in target_node else LootCategory.ACCESS,
            confidence=1.0,
            discovered_by=strategist_id,
        )
        delta_p = self.graph.commit_loot(loot, [target_node])
        action_log.append(f"防线击穿！节点 [{target_node}] 状态转为达成。攻击图边际进度 ΔP = {delta_p * 100:.1f}%。")

        # 4. Award bounty points
        new_total = self.ledger.reward_points(strategist_id, bounty_reward)
        action_log.append(f"突防成功！斩获高额赏金 +{bounty_reward} 积分！当前累计总积分: {new_total:.1f}。")

        # 5. Capture command leadership
        lead_captured = False
        handover = self.ledger.force_lead_capture(
            strategist_id,
            f"战术肉搏攻破高价值节点 '{target_node}' (ΔP: {delta_p*100:.1f}%, +{bounty_reward} pts)",
        )
        if handover:
            lead_captured = True
            action_log.append(f"触发临场换帅！{strategist_id} 凭肉搏战果直接接掌战场总指挥权！")

        result = TacticalCombatResult(
            combat_id=combat_id,
            round_number=self.current_round,
            strategist_id=strategist_id,
            target_node=target_node,
            points_cost=cost_points,
            success=True,
            reward_points=bounty_reward,
            delta_p=delta_p,
            knowledge_references=knowledge_refs,
            action_log=action_log,
            lead_captured=lead_captured,
        )

        self.event_log.append({
            "type": "tactical_combat",
            "combat_id": combat_id,
            "round": self.current_round,
            "strategist_id": strategist_id,
            "target_node": target_node,
            "delta_p": delta_p,
            "success": True,
            "lead_captured": lead_captured,
            "summary": f"战略家 {strategist_id} 亲自下场攻破 {target_node} (ΔP: {delta_p*100:.1f}%)",
        })
        return result

    def get_status(self) -> Dict[str, Any]:
        return {
            "round": self.current_round,
            "circuit_state": self.circuit_state.value,
            "graph": self.graph.snapshot(),
            "ledger": self.ledger.to_dict(),
            "recent_events": self.event_log[-10:],
        }
