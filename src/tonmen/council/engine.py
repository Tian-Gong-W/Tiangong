from __future__ import annotations

from uuid import uuid4

from tonmen.evidence import GraphNode
from tonmen.missions import MissionPlan, MissionRun, MissionRunState, StepExecutionState


_FOCI = (
    "scope_and_plan",
    "network_surface",
    "web_surface",
    "evidence_integrity",
    "vulnerability_validation",
    "attribution_review",
    "risk_and_impact",
    "remediation",
    "residual_risk",
    "final_synthesis",
)

_ROLES = (
    "surface_mapper",
    "evidence_verifier",
    "vulnerability_analyst",
    "governance_reviewer",
    "remediation_editor",
)


class AssessmentCouncil:
    """Evidence-only subagent council.

    Council members never execute tools, expand Scope, issue approvals, or mutate the
    mission plan. They only inspect already-recorded plan/run/evidence graph state and
    add review provenance nodes to the graph.
    """

    def __init__(self, *, target_rounds: int = 8, agents_per_round: int = 4) -> None:
        if not 7 <= int(target_rounds) <= 10:
            raise ValueError("assessment_rounds must be between 7 and 10")
        if not 3 <= int(agents_per_round) <= 5:
            raise ValueError("subagents_per_round must be between 3 and 5")
        self.target_rounds = int(target_rounds)
        self.agents_per_round = int(agents_per_round)

    @staticmethod
    def _existing_rounds(run: MissionRun) -> int:
        return sum(1 for node in run.graph.nodes.values() if node.kind == "council.round")

    @staticmethod
    def _fact_nodes(run: MissionRun):
        return [node for node in run.graph.nodes.values() if node.kind.startswith("intelligence.")]

    @staticmethod
    def _finding_nodes(run: MissionRun):
        return [node for node in run.graph.nodes.values() if node.kind == "intelligence.finding"]

    @staticmethod
    def _recommended_action(run: MissionRun) -> str:
        if run.state is MissionRunState.WAITING_APPROVAL:
            return "await_human_approval"
        if run.state in {MissionRunState.FAILED, MissionRunState.DENIED}:
            return "review_failure_evidence"
        if run.state is MissionRunState.SUCCEEDED:
            return "finalize_report"
        return "continue_governed_plan"

    def _summary(self, role: str, plan: MissionPlan, run: MissionRun, focus: str) -> tuple[str, tuple[str, ...], tuple[str, ...]]:
        evidence_ids = tuple(item.id for item in run.evidence)
        facts = self._fact_nodes(run)
        fact_ids = tuple(node.id for node in facts)
        findings = self._finding_nodes(run)
        failed = [step for step in run.steps if step.state in {StepExecutionState.FAILED, StepExecutionState.DENIED}]
        degraded = [step for step in run.steps if step.state is StepExecutionState.DEGRADED]
        waiting = [step for step in run.steps if step.state is StepExecutionState.WAITING_APPROVAL]
        completed = [step for step in run.steps if step.state is StepExecutionState.SUCCEEDED]

        if role == "surface_mapper":
            summary = (
                f"{focus}: target {plan.target}; {len(completed)}/{len(run.steps)} steps completed; "
                f"{len(facts)} evidence-backed facts and {len(run.evidence)} evidence records available."
            )
        elif role == "evidence_verifier":
            nonzero = sum(1 for item in run.evidence if item.exit_code != 0)
            summary = (
                f"{focus}: provenance review sees {len(run.evidence)} evidence records, {nonzero} non-zero exits, "
                f"{len(degraded)} degraded steps and {len(failed)} failed/denied steps."
            )
        elif role == "vulnerability_analyst":
            severities = [str(node.metadata.get("severity", "info")) for node in findings]
            summary = (
                f"{focus}: {len(findings)} finding facts currently supported; severities="
                f"{','.join(severities) if severities else 'none'}; template matches remain distinct from root-cause attribution."
            )
        elif role == "governance_reviewer":
            approval_steps = sum(1 for step in plan.steps if step.requires_approval)
            summary = (
                f"{focus}: {approval_steps} planned approval-gated steps, {len(waiting)} currently waiting; "
                "Scope/Policy/Approval remain the only execution authority."
            )
        else:
            summary = (
                f"{focus}: remediation synthesis based on {len(findings)} findings, {len(failed)} failed/denied steps, "
                f"and mission state {run.state.value}; recommendations must remain evidence-linked."
            )
        return summary, evidence_ids, fact_ids

    def record_round(
        self,
        plan: MissionPlan,
        run: MissionRun,
        *,
        session_id: str,
        phase: str,
        decision_id: str | None = None,
    ) -> str | None:
        current = self._existing_rounds(run)
        if current >= self.target_rounds:
            return None
        round_number = current + 1
        focus = _FOCI[round_number - 1]
        round_id = uuid4().hex
        run.graph.add_node(
            GraphNode(
                id=round_id,
                kind="council.round",
                label=f"assessment round {round_number}: {focus}",
                metadata={
                    "round": round_number,
                    "focus": focus,
                    "phase": phase,
                    "agents": self.agents_per_round,
                    "session_id": session_id,
                    "decision_id": decision_id,
                },
            )
        )
        run.graph.link(run.id, "reviewed_in", round_id)
        if session_id in run.graph.nodes:
            run.graph.link(session_id, "contains_assessment_round", round_id)
        if decision_id and decision_id in run.graph.nodes:
            run.graph.link(decision_id, "reviewed_by", round_id)

        start = (round_number - 1) % len(_ROLES)
        roles = tuple(_ROLES[(start + index) % len(_ROLES)] for index in range(self.agents_per_round))
        action = self._recommended_action(run)
        for role in roles:
            summary, evidence_ids, fact_ids = self._summary(role, plan, run, focus)
            agent_id = uuid4().hex
            run.graph.add_node(
                GraphNode(
                    id=agent_id,
                    kind="council.subagent",
                    label=f"{role}: {summary}",
                    metadata={
                        "role": role,
                        "round": round_number,
                        "focus": focus,
                        "phase": phase,
                        "summary": summary,
                        "recommended_action": action,
                        "evidence_ids": list(evidence_ids),
                        "fact_ids": list(fact_ids),
                        "execution_authority": False,
                    },
                )
            )
            run.graph.link(round_id, "contains_subagent", agent_id)
            for evidence_id in evidence_ids[-8:]:
                if evidence_id in run.graph.nodes:
                    run.graph.link(evidence_id, "reviewed_by", agent_id)
            for fact_id in fact_ids[-12:]:
                if fact_id in run.graph.nodes:
                    run.graph.link(fact_id, "reviewed_by", agent_id)
        return round_id

    def complete_terminal_review(self, plan: MissionPlan, run: MissionRun, *, session_id: str) -> int:
        """Fill remaining review rounds only after a terminal mission state.

        This satisfies the 7-10 round assessment contract without repeating network
        or validation commands after the mission has already reached a terminal state.
        """
        if run.state not in {MissionRunState.SUCCEEDED, MissionRunState.FAILED, MissionRunState.DENIED}:
            return 0
        added = 0
        while self._existing_rounds(run) < self.target_rounds:
            if self.record_round(plan, run, session_id=session_id, phase="post_execution") is None:
                break
            added += 1
        return added
