from __future__ import annotations

from uuid import uuid4

from tonmen.adaptive import assess_evidence_confidence, build_target_profile, desired_assessment_rounds, select_agent_roster
from tonmen.evidence import GraphNode
from tonmen.missions import MissionPlan, MissionRun, MissionRunState, StepExecutionState


_FOCI = (
    "scope_and_plan",
    "network_surface",
    "web_surface",
    "evidence_integrity",
    "validation_coverage",
    "attribution_review",
    "risk_and_impact",
    "remediation",
    "residual_risk",
    "final_synthesis",
)


class AssessmentCouncil:
    """Evidence-only adaptive subagent council.

    Council composition changes with the live target profile and explicit evidence
    conflicts, but the governance envelope is fixed: 7-10 rounds and 3-5 read-only
    subagents per round. Members never execute tools, expand Scope, issue approvals,
    or mutate the mission plan.
    """

    def __init__(
        self,
        *,
        target_rounds: int = 8,
        agents_per_round: int = 4,
        min_rounds: int = 7,
        max_rounds: int = 10,
        min_agents: int = 3,
        max_agents: int = 5,
    ) -> None:
        if not 7 <= int(min_rounds) <= int(target_rounds) <= int(max_rounds) <= 10:
            raise ValueError("assessment rounds must stay within 7-10")
        if not 3 <= int(min_agents) <= int(agents_per_round) <= int(max_agents) <= 5:
            raise ValueError("subagents per round must stay within 3-5")
        self.target_rounds = int(target_rounds)
        self.agents_per_round = int(agents_per_round)
        self.min_rounds = int(min_rounds)
        self.max_rounds = int(max_rounds)
        self.min_agents = int(min_agents)
        self.max_agents = int(max_agents)

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
        return "continue_evidence_driven_plan"

    def _summary(self, role: str, plan: MissionPlan, run: MissionRun, focus: str) -> tuple[str, tuple[str, ...], tuple[str, ...]]:
        evidence_ids = tuple(item.id for item in run.evidence)
        facts = self._fact_nodes(run)
        fact_ids = tuple(node.id for node in facts)
        findings = self._finding_nodes(run)
        profile = build_target_profile(plan, run)
        confidence = assess_evidence_confidence(plan, run)
        failed = [step for step in run.steps if step.state in {StepExecutionState.FAILED, StepExecutionState.DENIED}]
        degraded = [step for step in run.steps if step.state is StepExecutionState.DEGRADED]
        waiting = [step for step in run.steps if step.state is StepExecutionState.WAITING_APPROVAL]
        completed = [step for step in run.steps if step.state is StepExecutionState.SUCCEEDED]

        if role == "conflict_analyst":
            subjects = ", ".join(item.subject for item in confidence.conflicted[:4]) or "none"
            summary = (
                f"{focus}: supported={len(confidence.supported)}, conflicted={len(confidence.conflicted)}, "
                f"unresolved={len(confidence.unresolved)}; conflict subjects={subjects}. "
                "Absence of evidence is not treated as contradictory evidence."
            )
            fact_ids = confidence.conflict_fact_ids or fact_ids
        elif role == "network_surface_mapper":
            summary = (
                f"{focus}: observed ports={','.join(str(port) for port in profile.ports) or 'none'}; "
                f"services={','.join(profile.services) or 'none'}; unknowns={','.join(profile.unknowns) or 'none'}."
            )
        elif role == "web_surface_analyst":
            summary = (
                f"{focus}: {len(profile.web_urls)} evidence-backed web locations, "
                f"technologies={','.join(profile.technologies) or 'unknown'}; profile complexity={profile.complexity}."
            )
        elif role == "api_analyst":
            api_hypothesis = next((item for item in profile.hypotheses if item.key == "api_surface"), None)
            summary = (
                f"{focus}: API-oriented evidence hypothesis confidence="
                f"{api_hypothesis.confidence if api_hypothesis else 0.0:.2f}; keep conclusions evidence-linked."
            )
        elif role == "evidence_verifier":
            nonzero = sum(1 for item in run.evidence if item.exit_code != 0)
            summary = (
                f"{focus}: provenance review sees {len(run.evidence)} evidence records, {nonzero} non-zero exits, "
                f"{len(degraded)} degraded steps, {len(failed)} failed/denied steps and "
                f"{len(confidence.conflicted)} explicit comparable-fact conflict(s)."
            )
        elif role == "vulnerability_analyst":
            severities = [str(node.metadata.get("severity", "info")) for node in findings]
            summary = (
                f"{focus}: {len(findings)} finding facts currently supported; severities="
                f"{','.join(severities) if severities else 'none'}; validation evidence remains distinct from root-cause attribution."
            )
        elif role == "impact_analyst":
            summary = (
                f"{focus}: {profile.severe_findings} high/critical finding(s); assess prerequisites, impact and residual risk "
                "without performing any final active action."
            )
        elif role == "governance_reviewer":
            approval_steps = sum(1 for step in plan.steps if step.requires_approval)
            summary = (
                f"{focus}: {approval_steps} planned approval-gated steps, {len(waiting)} currently waiting; "
                "Scope/Policy/Approval remain the only execution authority."
            )
        elif role == "remediation_editor":
            summary = (
                f"{focus}: remediation synthesis based on {len(findings)} findings, {len(failed)} failed/denied steps, "
                f"and mission state {run.state.value}; recommendations must remain evidence-linked."
            )
        else:
            summary = (
                f"{focus}: target {plan.target}; {len(completed)}/{len(run.steps)} steps completed; "
                f"{len(facts)} evidence-backed facts and {len(run.evidence)} evidence records available."
            )
        return summary, evidence_ids, fact_ids

    def _desired_rounds(self, plan: MissionPlan, run: MissionRun) -> int:
        rounds = desired_assessment_rounds(
            build_target_profile(plan, run),
            minimum=self.min_rounds,
            preferred=self.target_rounds,
            maximum=self.max_rounds,
        )
        if assess_evidence_confidence(plan, run).conflicted:
            rounds += 1
        return max(self.min_rounds, min(self.max_rounds, rounds))

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
        desired_rounds = self._desired_rounds(plan, run)
        if current >= desired_rounds:
            return None
        round_number = current + 1
        focus = _FOCI[min(round_number - 1, len(_FOCI) - 1)]
        profile = build_target_profile(plan, run)
        confidence = assess_evidence_confidence(plan, run)
        roster = select_agent_roster(
            plan,
            run,
            min_agents=self.min_agents,
            preferred_agents=self.agents_per_round,
            max_agents=self.max_agents,
        )
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
                    "agents": len(roster),
                    "roles": [item.role for item in roster],
                    "session_id": session_id,
                    "decision_id": decision_id,
                    "target_profile": {
                        "kind": profile.target_kind,
                        "complexity": profile.complexity,
                        "unknowns": list(profile.unknowns),
                        "hypotheses": [item.key for item in profile.hypotheses],
                    },
                    "evidence_confidence": {
                        "supported": len(confidence.supported),
                        "conflicted": len(confidence.conflicted),
                        "unresolved": len(confidence.unresolved),
                        "conflict_keys": [item.key for item in confidence.conflicted],
                        "conflict_fact_ids": list(confidence.conflict_fact_ids),
                    },
                    "desired_rounds": desired_rounds,
                },
            )
        )
        run.graph.link(run.id, "reviewed_in", round_id)
        if session_id in run.graph.nodes:
            run.graph.link(session_id, "contains_assessment_round", round_id)
        if decision_id and decision_id in run.graph.nodes:
            run.graph.link(decision_id, "reviewed_by", round_id)

        action = self._recommended_action(run)
        for assignment in roster:
            role = assignment.role
            summary, evidence_ids, fact_ids = self._summary(role, plan, run, assignment.focus)
            agent_id = uuid4().hex
            run.graph.add_node(
                GraphNode(
                    id=agent_id,
                    kind="council.subagent",
                    label=f"{role}: {summary}",
                    metadata={
                        "role": role,
                        "round": round_number,
                        "focus": assignment.focus,
                        "phase": phase,
                        "summary": summary,
                        "recommended_action": action,
                        "evidence_ids": list(evidence_ids),
                        "fact_ids": list(fact_ids),
                        "execution_authority": False,
                        "report_only": True,
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
        """Fill the remaining evidence-review rounds only after terminal execution."""
        if run.state not in {MissionRunState.SUCCEEDED, MissionRunState.FAILED, MissionRunState.DENIED}:
            return 0
        added = 0
        while self._existing_rounds(run) < self._desired_rounds(plan, run):
            if self.record_round(plan, run, session_id=session_id, phase="post_execution") is None:
                break
            added += 1
        return added
