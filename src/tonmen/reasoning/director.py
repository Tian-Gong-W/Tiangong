from __future__ import annotations

from typing import Mapping

from tonmen.missions import MissionPlan, MissionRun, iter_plan_executions

from .engine import MissionReasoner
from .model import ReasoningAction, ReasoningDecision


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
        decision = self.reasoner.decide(plan, run)
        tokens = approval_tokens or {}

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
