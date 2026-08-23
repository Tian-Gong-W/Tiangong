from __future__ import annotations

from uuid import uuid4

from tonmen.adaptive import assess_evidence_confidence, build_target_profile, desired_assessment_rounds, select_agent_roster
from tonmen.evidence import GraphNode
from tonmen.missions import MissionPlan, MissionRun, MissionRunState, StepExecutionState
from tonmen.models import ModelRuntime, ModelRuntimeError


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

    Council composition changes with the live target profile, explicit evidence
    conflicts, and optional local AI advisory provenance. When a local model runtime
    is configured, each selected role receives an independent structured model review.
    The governance envelope is fixed: 7-10 rounds and 3-5 read-only subagents per
    round. Members never execute tools, expand Scope, issue approvals, or mutate the
    mission plan; model output remains advisory and has no execution authority.
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
        model_runtime: ModelRuntime | None = None,
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
        self.model_runtime = model_runtime or ModelRuntime()

    @staticmethod
    def _existing_rounds(run: MissionRun) -> int:
        return sum(1 for node in run.graph.nodes.values() if node.kind == "council.round")

    @staticmethod
    def _model_calls_used(run: MissionRun) -> int:
        return sum(1 for node in run.graph.nodes.values() if node.kind == "model.call")

    @staticmethod
    def _fact_nodes(run: MissionRun):
        return [node for node in run.graph.nodes.values() if node.kind.startswith("intelligence.")]

    @staticmethod
    def _finding_nodes(run: MissionRun):
        return [node for node in run.graph.nodes.values() if node.kind == "intelligence.finding"]

    @staticmethod
    def _latest_ai_advisory(run: MissionRun):
        advisories = [node for node in run.graph.nodes.values() if node.kind == "ai.advisory"]
        return advisories[-1] if advisories else None

    @staticmethod
    def _recommended_action(run: MissionRun) -> str:
        if run.state is MissionRunState.WAITING_APPROVAL:
            return "await_human_approval"
        if run.state in {MissionRunState.FAILED, MissionRunState.DENIED}:
            return "review_failure_evidence"
        if run.state is MissionRunState.SUCCEEDED:
            return "finalize_report"
        return "continue_evidence_driven_plan"

    @staticmethod
    def _profile_payload(profile) -> dict[str, object]:
        return {
            "target_kind": profile.target_kind,
            "complexity": profile.complexity,
            "ports": list(profile.ports),
            "services": list(profile.services),
            "web_urls": list(profile.web_urls),
            "technologies": list(profile.technologies),
            "findings": list(profile.findings),
            "severities": list(profile.severities),
            "unknowns": list(profile.unknowns),
            "hypotheses": [item.key for item in profile.hypotheses],
        }

    @staticmethod
    def _allowed_capabilities(plan: MissionPlan) -> tuple[str, ...]:
        return tuple(dict.fromkeys(step.tool for step in plan.steps))

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
        elif role == "ai_advisory_reviewer":
            advisory = self._latest_ai_advisory(run)
            if advisory is None:
                summary = f"{focus}: no local AI advisory is recorded; deterministic evidence analysis remains authoritative."
                fact_ids = ()
            else:
                metadata = advisory.metadata
                basis = tuple(
                    fact_id
                    for fact_id in metadata.get("basis_fact_ids", [])
                    if fact_id in run.graph.nodes
                )
                hypotheses = metadata.get("hypotheses", [])
                summary = (
                    f"{focus}: local {metadata.get('provider', 'AI')}/{metadata.get('model', 'model')} advisory "
                    f"has {len(hypotheses)} hypothesis item(s), challenge={bool(metadata.get('challenge_decision', False))}; "
                    f"review Fact basis before accepting any analytical claim. execution_authority=false."
                )
                fact_ids = basis
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

    def _model_review(self, plan: MissionPlan, run: MissionRun, *, role: str, focus: str):
        if not self.model_runtime.enabled:
            return None, None
        profile = build_target_profile(plan, run)
        calls_before = self._model_calls_used(run)
        try:
            review = self.model_runtime.review(
                role=role,
                focus=focus,
                target_profile=self._profile_payload(profile),
                allowed_capabilities=self._allowed_capabilities(plan),
                calls_already_used=calls_before,
            )
        except ModelRuntimeError as exc:
            return None, str(exc)
        return review, None

    def _record_model_call(self, run: MissionRun, *, agent_id: str, review, error: str | None) -> str:
        call_id = uuid4().hex
        status = "success" if review is not None else "fallback"
        metadata = {
            "provider": self.model_runtime.config.provider,
            "model": self.model_runtime.config.model,
            "status": status,
            "error": error,
            "execution_authority": False,
            "report_only": True,
        }
        if review is not None:
            metadata.update(
                {
                    "prompt_tokens": review.prompt_tokens,
                    "output_tokens": review.output_tokens,
                    "confidence": review.confidence,
                    "recommended_capabilities": list(review.recommended_capabilities),
                }
            )
        run.graph.add_node(
            GraphNode(
                id=call_id,
                kind="model.call",
                label=f"{self.model_runtime.config.provider}:{self.model_runtime.config.model}:{status}",
                metadata=metadata,
            )
        )
        run.graph.link(call_id, "supports_subagent", agent_id)
        return call_id

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
        ai_advisory = self._latest_ai_advisory(run)
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
                    "agent_mode": "model" if self.model_runtime.enabled else "deterministic",
                    "model_provider": self.model_runtime.config.provider,
                    "model_name": self.model_runtime.config.model,
                    "model_call_budget": self.model_runtime.config.max_calls,
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
                    "local_ai_advisory": (
                        {
                            "id": ai_advisory.id,
                            "provider": ai_advisory.metadata.get("provider"),
                            "model": ai_advisory.metadata.get("model"),
                            "challenge_decision": bool(ai_advisory.metadata.get("challenge_decision", False)),
                            "basis_fact_ids": list(ai_advisory.metadata.get("basis_fact_ids", [])),
                            "execution_authority": False,
                        }
                        if ai_advisory is not None
                        else None
                    ),
                    "desired_rounds": desired_rounds,
                },
            )
        )
        run.graph.link(run.id, "reviewed_in", round_id)
        if session_id in run.graph.nodes:
            run.graph.link(session_id, "contains_assessment_round", round_id)
        if decision_id and decision_id in run.graph.nodes:
            run.graph.link(decision_id, "reviewed_by", round_id)
        if ai_advisory is not None:
            run.graph.link(ai_advisory.id, "reviewed_in", round_id)

        action = self._recommended_action(run)
        for assignment in roster:
            role = assignment.role
            deterministic_summary, evidence_ids, fact_ids = self._summary(role, plan, run, assignment.focus)
            model_review, model_error = self._model_review(
                plan,
                run,
                role=role,
                focus=assignment.focus,
            )
            summary = model_review.summary if model_review is not None else deterministic_summary
            agent_id = uuid4().hex
            metadata = {
                "role": role,
                "round": round_number,
                "focus": assignment.focus,
                "phase": phase,
                "summary": summary,
                "deterministic_summary": deterministic_summary,
                "recommended_action": action,
                "evidence_ids": list(evidence_ids),
                "fact_ids": list(fact_ids),
                "execution_authority": False,
                "report_only": True,
                "agent_mode": "model" if model_review is not None else "deterministic",
            }
            if model_review is not None:
                metadata.update(
                    {
                        "model_observations": list(model_review.observations),
                        "model_risks": list(model_review.risks),
                        "model_next_questions": list(model_review.next_questions),
                        "model_recommended_capabilities": list(model_review.recommended_capabilities),
                        "model_confidence": model_review.confidence,
                    }
                )
            if model_error:
                metadata["model_error"] = model_error
            run.graph.add_node(
                GraphNode(
                    id=agent_id,
                    kind="council.subagent",
                    label=f"{role}: {summary}",
                    metadata=metadata,
                )
            )
            run.graph.link(round_id, "contains_subagent", agent_id)
            if self.model_runtime.enabled:
                self._record_model_call(run, agent_id=agent_id, review=model_review, error=model_error)
            if role == "ai_advisory_reviewer" and ai_advisory is not None:
                run.graph.link(ai_advisory.id, "reviewed_by", agent_id)
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
