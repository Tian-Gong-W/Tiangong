from __future__ import annotations

from typing import Mapping

from tonmen.missions import MissionPlan, MissionRun, StepExecutionState, iter_plan_executions

from .engine import MissionReasoner
from .model import ActionProposal, ReasoningAction, ReasoningDecision


class MissionDirector:
    """Authoritative next-action decision boundary for a mission.

    The Director owns the runtime question "what should happen next?". The
    current implementation delegates world-model reasoning to ``MissionReasoner``
    and adds pre-execution governance awareness while TONMEN migrates away from
    frozen ``MissionPlan.steps``. It deliberately reuses the existing hypothesis
    and action models instead of creating a second reasoning stack.
    """

    def __init__(self, reasoner: MissionReasoner | None = None) -> None:
        self.reasoner = reasoner or MissionReasoner()

    @staticmethod
    def _planned_step(plan: MissionPlan, run: MissionRun, step_id: str):
        for planned, execution in iter_plan_executions(plan, run):
            if planned.id == step_id:
                return planned, execution
        return None

    @staticmethod
    def _waiting_dynamic(run: MissionRun):
        for execution in run.steps:
            if execution.state is not StepExecutionState.WAITING_APPROVAL:
                continue
            if not bool(execution.metadata.get("dynamic")):
                continue
            return execution
        return None

    @staticmethod
    def _proposal_from_graph(run: MissionRun, proposal_id: str) -> ActionProposal | None:
        node = run.graph.nodes.get(proposal_id)
        if node is None or node.kind != "action_proposal":
            return None
        metadata = dict(node.metadata)
        parameters = metadata.get("parameters")
        if not isinstance(parameters, dict):
            parameters = {}
        return ActionProposal(
            id=proposal_id,
            tool=str(metadata.get("tool") or ""),
            target=str(metadata.get("target") or run.target),
            parameters=dict(parameters),
            rationale=str(metadata.get("rationale") or "Resume approved dynamic action."),
            expected_info_gain=float(metadata.get("expected_info_gain") or 0.0),
            risk=int(metadata.get("risk") or 1),
            requires_approval=bool(metadata.get("requires_approval", True)),
            hypothesis_id=str(metadata.get("hypothesis_id")) if metadata.get("hypothesis_id") else None,
            estimated_cost=max(1, int(metadata.get("estimated_cost") or 1)),
            metadata={
                key: value
                for key, value in metadata.items()
                if key
                not in {
                    "tool",
                    "target",
                    "parameters",
                    "rationale",
                    "expected_info_gain",
                    "risk",
                    "requires_approval",
                    "hypothesis_id",
                    "estimated_cost",
                    "status",
                }
            },
        )

    @staticmethod
    def _approval_basis(run: MissionRun, tool: str):
        facts = [node for node in run.graph.nodes.values() if node.kind.startswith("intelligence.")]
        if tool != "nuclei":
            return facts[:16]
        web_facts = [node for node in facts if node.kind == "intelligence.web"]
        http_services = []
        for node in facts:
            if node.kind != "intelligence.service":
                continue
            data = node.metadata.get("data", {})
            service = str(data.get("service", "")).lower() if isinstance(data, dict) else ""
            if "http" in service:
                http_services.append(node)
        return (web_facts + http_services)[:16]

    def decide_next(
        self,
        plan: MissionPlan,
        run: MissionRun,
        *,
        approval_tokens: Mapping[str, str] | None = None,
    ) -> ReasoningDecision:
        tokens = approval_tokens or {}

        # A late-bound ActionProposal is a first-class resumable action. Do not let
        # the legacy reasoner forget it simply because it is absent from
        # MissionPlan.steps.
        waiting_dynamic = self._waiting_dynamic(run)
        if waiting_dynamic is not None:
            proposal_id = str(waiting_dynamic.metadata.get("proposal_id") or "")
            proposal = self._proposal_from_graph(run, proposal_id) if proposal_id else None
            if proposal is None:
                return ReasoningDecision.create(
                    action=ReasoningAction.REVIEW,
                    summary="A dynamic action is waiting for approval but its proposal record is missing.",
                    next_step_id=waiting_dynamic.id,
                    requires_human=True,
                )
            if tokens.get(waiting_dynamic.id):
                return ReasoningDecision.create(
                    action=ReasoningAction.PROPOSE,
                    summary="A bound approval grant is present; resume the exact approved dynamic action.",
                    next_step_id=waiting_dynamic.id,
                    new_proposals=(proposal,),
                )
            return ReasoningDecision.create(
                action=ReasoningAction.REQUEST_APPROVAL,
                summary=f"{proposal.tool} is approval-gated; a bound grant is required before this dynamic action can run.",
                next_step_id=waiting_dynamic.id,
                requires_human=True,
            )

        decision = self.reasoner.decide(plan, run)

        if decision.action is ReasoningAction.REQUEST_APPROVAL:
            if decision.next_step_id and tokens.get(decision.next_step_id):
                return ReasoningDecision.create(
                    action=ReasoningAction.CONTINUE,
                    summary="A bound approval grant is present; execute the approved governed action.",
                    basis_fact_ids=decision.basis_fact_ids,
                    next_step_id=decision.next_step_id,
                    hypotheses=decision.hypotheses,
                )
            return decision

        if decision.action is not ReasoningAction.CONTINUE or not decision.next_step_id:
            return decision

        pair = self._planned_step(plan, run, decision.next_step_id)
        if pair is None:
            return decision
        planned, _ = pair
        if not planned.requires_approval or tokens.get(planned.id):
            return decision

        basis = self._approval_basis(run, planned.tool)
        if planned.tool == "nuclei" and not basis:
            return ReasoningDecision.create(
                action=ReasoningAction.SKIP,
                summary="No evidence-backed web surface supports vulnerability validation; skip the validation step.",
                next_step_id=planned.id,
                hypotheses=decision.hypotheses,
            )

        return ReasoningDecision.create(
            action=ReasoningAction.REQUEST_APPROVAL,
            summary=(
                "A web surface is confirmed by evidence; validation may add useful evidence but requires explicit human approval."
                if planned.tool == "nuclei"
                else f"{planned.tool} is approval-gated; only a human may authorize this planned step."
            ),
            basis_fact_ids=tuple(node.id for node in basis),
            next_step_id=planned.id,
            requires_human=True,
            hypotheses=decision.hypotheses,
        )
