from __future__ import annotations

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


class MissionReasoner:
    """Deterministic reasoning over provenance-linked facts and existing plan steps only."""

    def decide(self, plan: MissionPlan, run: MissionRun) -> ReasoningDecision:
        if run.plan_id != plan.id:
            raise ValueError("mission run does not belong to this plan")

        facts = _intelligence_nodes(run)

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
                web_facts = [node for node in facts if node.kind == "intelligence.web"]
                http_services = []
                for node in facts:
                    if node.kind != "intelligence.service":
                        continue
                    data = node.metadata.get("data", {})
                    service = str(data.get("service", "")).lower() if isinstance(data, dict) else ""
                    if "http" in service:
                        http_services.append(node)
                basis = web_facts + http_services
                if not basis:
                    return ReasoningDecision.create(
                        action=ReasoningAction.SKIP,
                        summary="No evidence-backed web surface supports vulnerability validation; skip the validation step.",
                        next_step_id=step.id,
                    )
                return ReasoningDecision.create(
                    action=ReasoningAction.REQUEST_APPROVAL,
                    summary="A web surface is confirmed by evidence; validation may add useful evidence but requires explicit human approval.",
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
            return ReasoningDecision.create(
                action=ReasoningAction.CONTINUE,
                summary=f"Continue with the next already-planned governed step: {step.tool}.",
                basis_fact_ids=tuple(node.id for node in facts[:16]),
                next_step_id=step.id,
            )

        severe = [
            node
            for node in facts
            if node.kind == "intelligence.finding" and str(node.metadata.get("severity", "")).lower() in _SEVERE
        ]
        if severe:
            return ReasoningDecision.create(
                action=ReasoningAction.REVIEW,
                summary=f"{len(severe)} high/critical evidence-backed finding(s) require human review.",
                basis_fact_ids=tuple(node.id for node in severe[:16]),
                requires_human=True,
            )

        return ReasoningDecision.create(
            action=ReasoningAction.COMPLETE,
            summary="No further planned action is justified by the current evidence.",
            basis_fact_ids=tuple(node.id for node in facts[:16]),
        )
