from __future__ import annotations

from tonmen.missions import MissionPlan, MissionRun, MissionRunState, StepExecutionState, iter_plan_executions

from .model import Hypothesis, HypothesisStatus, ReasoningAction, ReasoningDecision

_SEVERE = {"high", "critical"}


def _intelligence_nodes(run: MissionRun):
    return [node for node in run.graph.nodes.values() if node.kind.startswith("intelligence.")]


def _waiting_pair(plan: MissionPlan, run: MissionRun):
    for planned, execution in iter_plan_executions(plan, run):
        if execution.state is StepExecutionState.WAITING_APPROVAL:
            return planned, execution
    return None


def _refresh_hypotheses_from_evidence(run: MissionRun, facts) -> list[Hypothesis]:
    updated: list[Hypothesis] = []
    fact_ids = {n.id for n in facts}
    service_or_web = [n for n in facts if n.kind in {"intelligence.service", "intelligence.web", "intelligence.host"}]

    for node in run.graph.nodes.values():
        if node.kind != "hypothesis":
            continue
        status_raw = str(node.metadata.get("status", "open")).lower()
        statement = node.label or str(node.metadata.get("statement") or "")
        confidence = float(node.metadata.get("confidence") or 0.4)
        supporting = tuple(node.metadata.get("supporting_fact_ids") or ())
        contradicting = tuple(node.metadata.get("contradicting_fact_ids") or ())

        if status_raw in {"supported", "contradicted", "abandoned"}:
            updated.append(
                Hypothesis(
                    id=node.id,
                    statement=statement,
                    confidence=confidence,
                    supporting_fact_ids=supporting,
                    contradicting_fact_ids=contradicting,
                    status=HypothesisStatus(status_raw),
                    metadata=dict(node.metadata),
                )
            )
            continue

        if str(node.metadata.get("kind") or "") in {"bootstrap", "surface_characterization"} or "passive services" in statement.lower() or "web surfaces" in statement.lower():
            if service_or_web:
                supporting = tuple(dict.fromkeys([*supporting, *[n.id for n in service_or_web[:8]]]))
                confidence = min(0.95, confidence + 0.25 * len(service_or_web))
                status = HypothesisStatus.SUPPORTED
            elif len(facts) >= 3:
                confidence = max(0.1, confidence - 0.15)
                status = HypothesisStatus.OPEN if confidence >= 0.25 else HypothesisStatus.ABANDONED
            else:
                status = HypothesisStatus.OPEN
        else:
            still_supported = [fid for fid in supporting if fid in fact_ids]
            if still_supported and confidence >= 0.6:
                status = HypothesisStatus.SUPPORTED
                supporting = tuple(still_supported)
            elif confidence < 0.2:
                status = HypothesisStatus.ABANDONED
            else:
                status = HypothesisStatus.OPEN

        updated.append(
            Hypothesis(
                id=node.id,
                statement=statement,
                confidence=confidence,
                supporting_fact_ids=supporting,
                contradicting_fact_ids=contradicting,
                status=status,
                metadata=dict(node.metadata),
            )
        )
    return updated


class MissionReasoner:
    """Reconcile evidence into hypothesis and mission state.

    Capability selection belongs to ``MissionDirector``. The reasoner retains
    terminal/review/approval interpretation and a legacy pending-step fallback while
    ``MissionPlan.steps`` remains a compatibility surface.
    """

    def decide(self, plan: MissionPlan, run: MissionRun) -> ReasoningDecision:
        if run.plan_id != plan.id:
            raise ValueError("mission run does not belong to this plan")

        facts = _intelligence_nodes(run)
        refreshed = _refresh_hypotheses_from_evidence(run, facts)

        if run.state in {MissionRunState.FAILED, MissionRunState.DENIED}:
            return ReasoningDecision.create(
                action=ReasoningAction.STOP,
                summary=f"Mission is terminal: {run.state.value}. No further action is justified.",
                requires_human=run.state is MissionRunState.FAILED,
                hypotheses=refreshed,
            )

        severe = [
            node for node in facts
            if node.kind == "intelligence.finding" and str(node.metadata.get("severity", "")).lower() in _SEVERE
        ]
        if severe:
            return ReasoningDecision.create(
                action=ReasoningAction.REVIEW,
                summary=f"{len(severe)} high/critical evidence-backed finding(s) require human review.",
                basis_fact_ids=tuple(node.id for node in severe[:16]),
                requires_human=True,
                hypotheses=refreshed,
            )

        waiting = _waiting_pair(plan, run)
        if waiting is not None:
            step, _ = waiting
            return ReasoningDecision.create(
                action=ReasoningAction.REQUEST_APPROVAL,
                summary=f"{step.tool} is approval-gated; a bound grant is required before this compatibility action can run.",
                basis_fact_ids=tuple(node.id for node in facts[:16]),
                next_step_id=step.id,
                requires_human=True,
                hypotheses=refreshed,
            )

        pending = [(p, e) for p, e in iter_plan_executions(plan, run) if e.state is StepExecutionState.PENDING]
        if pending:
            step, _ = pending[0]
            return ReasoningDecision.create(
                action=ReasoningAction.CONTINUE,
                summary=f"Compatibility fallback has a pending governed action: {step.tool}.",
                basis_fact_ids=tuple(node.id for node in facts[:16]),
                next_step_id=step.id,
                hypotheses=refreshed,
            )

        open_left = [h for h in refreshed if h.status is HypothesisStatus.OPEN and h.confidence >= 0.25]
        return ReasoningDecision.create(
            action=ReasoningAction.COMPLETE,
            summary=(
                "World-model reconciliation is complete; capability selection belongs to the Mission Director."
                if open_left else "No open high-value hypothesis remains after evidence reconciliation."
            ),
            basis_fact_ids=tuple(node.id for node in facts[:16]),
            hypotheses=refreshed,
        )
