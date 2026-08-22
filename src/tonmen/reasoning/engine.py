from __future__ import annotations

from tonmen.missions import MissionPlan, MissionRun, MissionRunState, StepExecutionState

from .model import ActionProposal, Hypothesis, HypothesisStatus, ReasoningAction, ReasoningDecision

_SEVERE = {"high", "critical"}


def _intelligence_nodes(run: MissionRun):
    return [node for node in run.graph.nodes.values() if node.kind.startswith("intelligence.")]


def _waiting_pair(plan: MissionPlan, run: MissionRun):
    for planned, execution in zip(plan.steps, run.steps, strict=True):
        if execution.state is StepExecutionState.WAITING_APPROVAL:
            return planned, execution
    return None


class MissionReasoner:
    """Reasoning over provenance-linked facts.

    Phase 1 change: in addition to selecting among the original frozen plan
    steps, the reasoner may emit new ActionProposals when the fixed plan is
    exhausted but uncertainty remains. Every proposal must still pass Scope,
    risk and approval checks before the loop schedules it.
    """

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

        # Phase 1: when the original plan is exhausted but we still have little
        # evidence, emit a low-risk follow-up proposal instead of immediately
        # completing. The loop will still subject it to Scope + risk + approval.
        proposals: list[ActionProposal] = []
        hypotheses: list[Hypothesis] = []

        if len(facts) < 3 and run.target:
            # Minimal self-reliant behaviour: if almost nothing is known, propose
            # a passive discovery step rather than declaring the mission done.
            hypo = Hypothesis.create(
                statement=f"Target {run.target} may expose additional passive services or web surfaces not yet observed.",
                confidence=0.4,
                status=HypothesisStatus.OPEN,
            )
            hypotheses.append(hypo)
            proposals.append(
                ActionProposal.create(
                    tool="nmap",
                    target=run.target,
                    parameters={"args": ["-sV", "-T4", "--top-ports", "100"]},
                    rationale="Original plan produced little intelligence; a passive service scan may increase world-model coverage at low risk.",
                    expected_info_gain=0.55,
                    risk=1,
                    requires_approval=False,
                    hypothesis_id=hypo.id,
                    estimated_cost=1,
                )
            )

        if proposals:
            return ReasoningDecision.create(
                action=ReasoningAction.PROPOSE,
                summary="Original plan exhausted; emitting new low-risk ActionProposal(s) to reduce residual uncertainty.",
                basis_fact_ids=tuple(node.id for node in facts[:16]),
                new_proposals=proposals,
                hypotheses=hypotheses,
            )

        return ReasoningDecision.create(
            action=ReasoningAction.COMPLETE,
            summary="No further planned action is justified by the current evidence, and no high-value new proposal was generated.",
            basis_fact_ids=tuple(node.id for node in facts[:16]),
        )
