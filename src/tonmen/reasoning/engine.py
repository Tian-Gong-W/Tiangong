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


def _already_tried_tools(run: MissionRun) -> set[tuple[str, str]]:
    """Tools already planned, proposed, or executed for a given target."""
    tried: set[tuple[str, str]] = set()
    for step in run.steps:
        tried.add((step.tool, step.target))
    for node in run.graph.nodes.values():
        if node.kind in {"action_proposal", "step", "step.dynamic"}:
            tool = str(node.metadata.get("tool") or "")
            target = str(node.metadata.get("target") or "")
            if not tool:
                # label form "tool:target"
                label = node.label or ""
                if ":" in label:
                    tool, _, target = label.partition(":")
            if tool and target:
                tried.add((tool, target))
    return tried


def _refresh_hypotheses_from_evidence(run: MissionRun, facts) -> list[Hypothesis]:
    """Re-evaluate open hypotheses against current intelligence nodes.

    Phase 2: evidence can support, contradict, or leave hypotheses open.
    We emit updated Hypothesis objects so the loop can rewrite graph metadata.
    """
    updated: list[Hypothesis] = []
    fact_ids = {n.id for n in facts}
    service_or_web = [
        n for n in facts if n.kind in {"intelligence.service", "intelligence.web", "intelligence.host"}
    ]

    for node in run.graph.nodes.values():
        if node.kind != "hypothesis":
            continue
        status_raw = str(node.metadata.get("status", "open")).lower()
        if status_raw in {"supported", "contradicted", "abandoned"}:
            continue

        statement = node.label or str(node.metadata.get("statement") or "")
        confidence = float(node.metadata.get("confidence") or 0.4)
        supporting = tuple(node.metadata.get("supporting_fact_ids") or ())
        contradicting = tuple(node.metadata.get("contradicting_fact_ids") or ())

        # Heuristic: passive-surface hypotheses become supported when we have
        # any service/web/host intelligence; otherwise stay open (or drop conf).
        if "passive services" in statement.lower() or "web surfaces" in statement.lower():
            if service_or_web:
                supporting = tuple(dict.fromkeys([*supporting, *[n.id for n in service_or_web[:8]]]))
                confidence = min(0.95, confidence + 0.25 * len(service_or_web))
                status = HypothesisStatus.SUPPORTED
            elif len(facts) >= 3:
                # Plenty of other facts but no surface evidence → weaken
                confidence = max(0.1, confidence - 0.15)
                status = HypothesisStatus.OPEN if confidence >= 0.25 else HypothesisStatus.ABANDONED
            else:
                status = HypothesisStatus.OPEN
        else:
            # Generic: if any linked supporting facts still exist, keep; else open
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
    """Reasoning over provenance-linked facts.

    Phase 2:
    - refresh hypothesis status from evidence
    - avoid re-proposing tools already tried for the same target
    - only emit proposals with meaningful expected information gain
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
                        hypotheses=refreshed,
                    )
                return ReasoningDecision.create(
                    action=ReasoningAction.REQUEST_APPROVAL,
                    summary="A web surface is confirmed by evidence; validation may add useful evidence but requires explicit human approval.",
                    basis_fact_ids=tuple(node.id for node in basis[:16]),
                    next_step_id=step.id,
                    requires_human=True,
                    hypotheses=refreshed,
                )

            return ReasoningDecision.create(
                action=ReasoningAction.REQUEST_APPROVAL,
                summary=f"{step.tool} is approval-gated; only a human may authorize this planned step.",
                basis_fact_ids=tuple(node.id for node in facts[:16]),
                next_step_id=step.id,
                requires_human=True,
                hypotheses=refreshed,
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
                hypotheses=refreshed,
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
                hypotheses=refreshed,
            )

        proposals: list[ActionProposal] = []
        new_hypotheses: list[Hypothesis] = list(refreshed)
        tried = _already_tried_tools(run)

        # Phase 2: only propose when residual uncertainty is real and the
        # candidate action has not already been attempted for this target.
        if len(facts) < 3 and run.target and ("nmap", run.target) not in tried:
            hypo = Hypothesis.create(
                statement=f"Target {run.target} may expose additional passive services or web surfaces not yet observed.",
                confidence=0.4,
                status=HypothesisStatus.OPEN,
            )
            new_hypotheses.append(hypo)
            proposals.append(
                ActionProposal.create(
                    tool="nmap",
                    target=run.target,
                    parameters={"args": ["-sV", "-T4", "--top-ports", "100"]},
                    rationale="Little intelligence so far; a passive service scan may increase world-model coverage at low risk.",
                    expected_info_gain=0.55 if len(facts) == 0 else 0.40,
                    risk=1,
                    requires_approval=False,
                    hypothesis_id=hypo.id,
                    estimated_cost=1,
                )
            )

        # If we already tried the low-risk follow-up and still have almost no
        # facts, do not keep re-proposing the same action — that is not autonomy,
        # that is a loop.
        if proposals:
            return ReasoningDecision.create(
                action=ReasoningAction.PROPOSE,
                summary="Residual uncertainty remains; emitting new low-risk ActionProposal(s).",
                basis_fact_ids=tuple(node.id for node in facts[:16]),
                new_proposals=proposals,
                hypotheses=new_hypotheses,
            )

        open_left = [
            h for h in new_hypotheses if h.status is HypothesisStatus.OPEN and h.confidence >= 0.25
        ]
        if not open_left:
            return ReasoningDecision.create(
                action=ReasoningAction.COMPLETE,
                summary="No open high-value hypotheses remain and no new proposal is justified.",
                basis_fact_ids=tuple(node.id for node in facts[:16]),
                hypotheses=new_hypotheses,
            )

        return ReasoningDecision.create(
            action=ReasoningAction.COMPLETE,
            summary="Open hypotheses remain but no safe high-info-gain action is available without a new capability or human direction.",
            basis_fact_ids=tuple(node.id for node in facts[:16]),
            hypotheses=new_hypotheses,
        )
