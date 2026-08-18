from __future__ import annotations

from tonmen.adaptive import assess_evidence_confidence, build_target_profile
from tonmen.missions import MissionPlan, MissionRun, MissionRunState, StepExecutionState

from .model import ReasoningAction, ReasoningDecision

_SEVERE = {"high", "critical"}


def _intelligence_nodes(run: MissionRun):
    return [node for node in run.graph.nodes.values() if node.kind.startswith("intelligence.")]


def _waiting_pair(plan: MissionPlan, run: MissionRun):
    for planned, execution in zip(plan.steps, run.steps, strict=True):
        if execution.state is StepExecutionState.WAITING_APPROVAL:
            return planned, execution
    return None


def _completed_tools(run: MissionRun) -> set[str]:
    return {
        step.tool
        for step in run.steps
        if step.state in {StepExecutionState.SUCCEEDED, StepExecutionState.DEGRADED, StepExecutionState.SKIPPED}
    }


class MissionReasoner:
    """Evidence-driven reasoning over governed plan capabilities.

    The reasoner may continue or skip candidate capabilities based on the live target
    profile. It never expands Scope, issues approvals, or creates executable shell text.
    Explicit conflicts between comparable persisted facts are surfaced for review rather
    than silently collapsed into a single conclusion.
    """

    def decide(self, plan: MissionPlan, run: MissionRun) -> ReasoningDecision:
        if run.plan_id != plan.id:
            raise ValueError("mission run does not belong to this plan")

        facts = _intelligence_nodes(run)
        profile = build_target_profile(plan, run)
        confidence = assess_evidence_confidence(plan, run)
        completed_tools = _completed_tools(run)

        if run.state in {MissionRunState.FAILED, MissionRunState.DENIED}:
            return ReasoningDecision.create(
                action=ReasoningAction.STOP,
                summary=f"Mission is terminal: {run.state.value}. No further action is justified.",
                requires_human=run.state is MissionRunState.FAILED,
            )

        waiting = _waiting_pair(plan, run)
        if waiting is not None:
            step, _ = waiting
            if step.tool == "nuclei":
                basis = [node for node in facts if node.kind in {"intelligence.web", "intelligence.service"}]
                if not profile.has_web_surface:
                    return ReasoningDecision.create(
                        action=ReasoningAction.SKIP,
                        summary="Current evidence does not support a web validation branch; skip this candidate capability.",
                        next_step_id=step.id,
                    )
                return ReasoningDecision.create(
                    action=ReasoningAction.REQUEST_APPROVAL,
                    summary="The live target profile supports a bounded validation branch; explicit human approval is still required.",
                    basis_fact_ids=tuple(node.id for node in basis[:16]),
                    next_step_id=step.id,
                    requires_human=True,
                )

            return ReasoningDecision.create(
                action=ReasoningAction.REQUEST_APPROVAL,
                summary=f"{step.tool} is approval-gated; only a human may authorize this planned step.",
                basis_fact_ids=tuple(node.id for node in facts[:16]),
                next_step_id=step.id,
                requires_human=True,
            )

        pending = [
            (planned, execution)
            for planned, execution in zip(plan.steps, run.steps, strict=True)
            if execution.state is StepExecutionState.PENDING
        ]
        if pending:
            step, _ = pending[0]

            if step.tool == "httpx" and "nmap" in completed_tools and profile.target_kind != "web":
                has_http_service = any("http" in service for service in profile.services)
                if profile.services and not has_http_service:
                    return ReasoningDecision.create(
                        action=ReasoningAction.SKIP,
                        summary="Network evidence does not show an HTTP-capable service; do not spend the web probe budget.",
                        basis_fact_ids=tuple(node.id for node in facts[:16]),
                        next_step_id=step.id,
                    )

            if step.tool == "crawler" and "httpx" in completed_tools:
                if not profile.has_web_surface:
                    return ReasoningDecision.create(
                        action=ReasoningAction.SKIP,
                        summary="No evidence-backed web surface remains after HTTP observation; skip crawling.",
                        basis_fact_ids=tuple(node.id for node in facts[:16]),
                        next_step_id=step.id,
                    )

            return ReasoningDecision.create(
                action=ReasoningAction.CONTINUE,
                summary=(
                    f"Continue with governed capability {step.tool}; current profile complexity={profile.complexity}, "
                    f"unknowns={','.join(profile.unknowns) if profile.unknowns else 'none'}, "
                    f"evidence_conflicts={len(confidence.conflicted)}."
                ),
                basis_fact_ids=tuple(node.id for node in facts[:16]),
                next_step_id=step.id,
            )

        if confidence.conflicted:
            conflict_ids = confidence.conflict_fact_ids
            labels = ", ".join(item.subject for item in confidence.conflicted[:3])
            return ReasoningDecision.create(
                action=ReasoningAction.REVIEW,
                summary=(
                    f"{len(confidence.conflicted)} explicit evidence conflict(s) remain ({labels}); "
                    "review corroboration before treating the target profile as converged."
                ),
                basis_fact_ids=conflict_ids[:16],
                requires_human=True,
            )

        severe = [
            node
            for node in facts
            if node.kind == "intelligence.finding" and str(node.metadata.get("severity", "")).lower() in _SEVERE
        ]
        if severe:
            return ReasoningDecision.create(
                action=ReasoningAction.REVIEW,
                summary=(
                    f"{len(severe)} high/critical evidence-backed finding(s) require impact and remediation review; "
                    "the report-only boundary prevents any final active action."
                ),
                basis_fact_ids=tuple(node.id for node in severe[:16]),
                requires_human=True,
            )

        return ReasoningDecision.create(
            action=ReasoningAction.COMPLETE,
            summary=(
                "No further governed candidate capability is justified and no explicit comparable-fact conflict remains; "
                "proceed to bounded assessment synthesis and reporting."
            ),
            basis_fact_ids=tuple(node.id for node in facts[:16]),
        )
