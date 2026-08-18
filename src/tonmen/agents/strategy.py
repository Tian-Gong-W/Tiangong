from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from tonmen.adaptive import build_target_profile
from tonmen.ai import AIProviderError
from tonmen.capabilities import CapabilityCandidate, CapabilityCatalog
from tonmen.core.runtime import TonmenRuntime
from tonmen.evidence import GraphNode
from tonmen.missions import MissionPlan, MissionRun, MissionRunState, MissionStep

from .planner import MissionPlanner


@dataclass(frozen=True, slots=True)
class PlanExpansion:
    """One evidence-backed capability addition; never an executable shell proposal."""

    step: MissionStep
    rationale: str
    expected_information_gain: str
    basis_fact_ids: tuple[str, ...]
    profile_unknowns: tuple[str, ...]
    deterministic_score: float = 0.0
    score_reasons: tuple[str, ...] = ()
    candidate_rankings: tuple[dict[str, Any], ...] = ()


class AdaptiveMissionPlanner:
    """Grow a mission one governed semantic capability at a time from evidence.

    Registered ToolSpecs declare their prerequisites, information gain and planning
    cost. CapabilityCatalog ranks those declarations against the current mission state.
    This planner therefore has no fixed tool chain. Optional local AI remains advisory
    only and cannot mutate ranking authority, Scope, Approval or REPORT_ONLY.
    """

    def __init__(self, runtime: TonmenRuntime) -> None:
        self.runtime = runtime
        self.base = MissionPlanner(runtime)
        self.catalog = CapabilityCatalog(runtime)

    def seed(self, target: str) -> MissionPlan:
        return self.base.seed(target)

    @staticmethod
    def _ai_snapshot(run: MissionRun) -> tuple[str, ...]:
        return tuple(item.id for item in run.evidence[-16:])

    def _record_local_ai_advisory(self, plan: MissionPlan, run: MissionRun) -> None:
        service = self.runtime.ai
        if service is None or not service.enabled or not run.evidence:
            return
        evidence_ids = self._ai_snapshot(run)
        if any(
            node.kind in {"ai.advisory", "ai.advisory_error"}
            and tuple(node.metadata.get("evidence_ids", ())) == evidence_ids
            for node in run.graph.nodes.values()
        ):
            return

        try:
            advisory = service.advise(plan, run)
        except (AIProviderError, ValueError, OSError) as exc:
            node_id = uuid4().hex
            run.graph.add_node(
                GraphNode(
                    id=node_id,
                    kind="ai.advisory_error",
                    label="local AI advisory unavailable; deterministic fallback retained",
                    metadata={
                        "provider": self.runtime.config.ai_provider,
                        "model": self.runtime.config.ai_model,
                        "error": str(exc)[:600],
                        "evidence_ids": list(evidence_ids),
                        "execution_authority": False,
                        "local_only": True,
                        "fallback": "deterministic",
                    },
                )
            )
            run.graph.link(run.id, "ai_fallback", node_id)
            if self.runtime.events is not None:
                self.runtime.events.publish(
                    "ai.advisory_failed",
                    mission_id=run.id,
                    plan_id=run.plan_id,
                    target=run.target,
                    provider=self.runtime.config.ai_provider,
                    model=self.runtime.config.ai_model,
                    error=str(exc)[:600],
                    deterministic_fallback=True,
                )
            return

        if advisory is None:
            return
        node_id = uuid4().hex
        hypotheses = [
            {
                "key": item.key,
                "summary": item.summary,
                "confidence": item.confidence,
                "basis_fact_ids": list(item.basis_fact_ids),
            }
            for item in advisory.hypotheses
        ]
        run.graph.add_node(
            GraphNode(
                id=node_id,
                kind="ai.advisory",
                label=advisory.summary or "local AI evidence advisory",
                metadata={
                    "provider": advisory.provider,
                    "model": advisory.model,
                    "phase": "pre_reasoning_advisory",
                    "summary": advisory.summary,
                    "focus": list(advisory.focus),
                    "hypotheses": hypotheses,
                    "challenge_decision": advisory.challenge_decision,
                    "challenge_reason": advisory.challenge_reason,
                    "basis_fact_ids": list(advisory.basis_fact_ids),
                    "evidence_ids": list(evidence_ids),
                    "execution_authority": False,
                    "local_only": advisory.local_only,
                    "api_key_required": False,
                },
            )
        )
        run.graph.link(run.id, "advised_by", node_id)
        for fact_id in advisory.basis_fact_ids:
            if fact_id in run.graph.nodes:
                run.graph.link(fact_id, "supports_ai_advisory", node_id)
        if self.runtime.events is not None:
            self.runtime.events.publish(
                "ai.advisory",
                mission_id=run.id,
                plan_id=run.plan_id,
                target=run.target,
                advisory_id=node_id,
                provider=advisory.provider,
                model=advisory.model,
                summary=advisory.summary,
                focus=list(advisory.focus),
                basis_fact_ids=list(advisory.basis_fact_ids),
                challenge_decision=advisory.challenge_decision,
                execution_authority=False,
                local_only=True,
            )

    def _build(self, plan: MissionPlan, run: MissionRun, candidate: CapabilityCandidate, rankings) -> PlanExpansion:
        step = self.base.build_step(
            candidate.tool,
            plan.target,
            parameters=candidate.parameters,
            rationale=candidate.rationale,
        )
        profile = build_target_profile(plan, run)
        return PlanExpansion(
            step=step,
            rationale=candidate.rationale,
            expected_information_gain=candidate.expected_information_gain,
            basis_fact_ids=candidate.basis_fact_ids,
            profile_unknowns=tuple(profile.unknowns),
            deterministic_score=candidate.score,
            score_reasons=candidate.reasons,
            candidate_rankings=tuple(item.audit_payload() for item in rankings[:8]),
        )

    def propose(self, plan: MissionPlan, run: MissionRun) -> PlanExpansion | None:
        if run.plan_id != plan.id:
            raise ValueError("mission run does not belong to this plan")
        if run.state in {MissionRunState.FAILED, MissionRunState.DENIED, MissionRunState.WAITING_APPROVAL}:
            return None

        self._record_local_ai_advisory(plan, run)
        rankings = self.catalog.rank(plan, run)
        candidate = next((item for item in rankings if item.eligible), None)
        if candidate is None:
            return None
        return self._build(plan, run, candidate, rankings)

    def apply(self, plan: MissionPlan, run: MissionRun, proposal: PlanExpansion) -> MissionPlan:
        """Append a proposal to immutable plan history and mutable run state."""
        revised = plan.extend([proposal.step])
        execution = run.append_planned_step(proposal.step)

        if proposal.step.id not in run.graph.nodes:
            run.graph.add_node(
                GraphNode(
                    id=proposal.step.id,
                    kind="step",
                    label=f"{proposal.step.tool}:{proposal.step.target}",
                    metadata={
                        "risk": proposal.step.risk,
                        "requires_approval": proposal.step.requires_approval,
                        "adaptive": True,
                    },
                )
            )
            run.graph.link(run.id, "contains", proposal.step.id)

        revision_id = uuid4().hex
        run.graph.add_node(
            GraphNode(
                id=revision_id,
                kind="planning.revision",
                label=f"adaptive plan + {proposal.step.tool}",
                metadata={
                    "tool": proposal.step.tool,
                    "target": proposal.step.target,
                    "risk": proposal.step.risk,
                    "requires_approval": proposal.step.requires_approval,
                    "rationale": proposal.rationale,
                    "expected_information_gain": proposal.expected_information_gain,
                    "basis_fact_ids": list(proposal.basis_fact_ids),
                    "profile_unknowns": list(proposal.profile_unknowns),
                    "deterministic_score": proposal.deterministic_score,
                    "score_reasons": list(proposal.score_reasons),
                    "candidate_rankings": list(proposal.candidate_rankings),
                    "selection_engine": "capability_catalog",
                    "execution_authority": False,
                },
            )
        )
        run.graph.link(run.id, "replanned_by", revision_id)
        run.graph.link(revision_id, "adds_step", proposal.step.id)
        for fact_id in proposal.basis_fact_ids:
            if fact_id in run.graph.nodes:
                run.graph.link(fact_id, "supports_plan_revision", revision_id)

        execution.metadata["plan_revision_id"] = revision_id
        execution.metadata["plan_rationale"] = proposal.rationale
        execution.metadata["expected_information_gain"] = proposal.expected_information_gain
        execution.metadata["basis_fact_ids"] = list(proposal.basis_fact_ids)
        execution.metadata["deterministic_score"] = proposal.deterministic_score
        execution.metadata["selection_engine"] = "capability_catalog"

        if self.runtime.events is not None:
            self.runtime.events.publish(
                "plan.revised",
                mission_id=run.id,
                plan_id=run.plan_id,
                target=run.target,
                revision_id=revision_id,
                step_id=proposal.step.id,
                tool=proposal.step.tool,
                step_target=proposal.step.target,
                risk=proposal.step.risk,
                requires_approval=proposal.step.requires_approval,
                rationale=proposal.rationale,
                expected_information_gain=proposal.expected_information_gain,
                deterministic_score=proposal.deterministic_score,
                score_reasons=list(proposal.score_reasons),
                selection_engine="capability_catalog",
                basis_fact_ids=list(proposal.basis_fact_ids),
            )
        return revised
