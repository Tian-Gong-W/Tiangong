from __future__ import annotations

from tonmen.missions import MissionPlan, MissionRun, MissionRunState, StepExecutionState

from .modalities import discriminating_experiment, next_modality_proposals
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
    tried: set[tuple[str, str]] = set()
    for step in run.steps:
        tried.add((step.tool, step.target))
    for node in run.graph.nodes.values():
        if node.kind in {"action_proposal", "step", "step.dynamic"}:
            tool = str(node.metadata.get("tool") or "")
            target = str(node.metadata.get("target") or "")
            if not tool:
                label = node.label or ""
                if ":" in label:
                    tool, _, target = label.partition(":")
            if tool and target:
                tried.add((tool, target))
    return tried


def _has_web_surface(facts) -> bool:
    for node in facts:
        if node.kind == "intelligence.web":
            return True
        if node.kind == "intelligence.service":
            data = node.metadata.get("data", {})
            service = str(data.get("service", "")).lower() if isinstance(data, dict) else ""
            if "http" in service:
                return True
    return False


def _refresh_hypotheses_from_evidence(run: MissionRun, facts) -> list[Hypothesis]:
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
        kind = str(node.metadata.get("kind") or "")

        if "passive services" in statement.lower() or "web surfaces" in statement.lower():
            if service_or_web:
                supporting = tuple(dict.fromkeys([*supporting, *[n.id for n in service_or_web[:8]]]))
                confidence = min(0.95, confidence + 0.25 * len(service_or_web))
                status = HypothesisStatus.SUPPORTED
            elif len(facts) >= 3:
                confidence = max(0.1, confidence - 0.15)
                status = HypothesisStatus.OPEN if confidence >= 0.25 else HypothesisStatus.ABANDONED
            else:
                status = HypothesisStatus.OPEN
        elif kind == "discriminating":
            # Discriminating meta-hypotheses resolve once we gain new surface facts
            if service_or_web:
                supporting = tuple(dict.fromkeys([*supporting, *[n.id for n in service_or_web[:4]]]))
                confidence = min(0.9, confidence + 0.3)
                status = HypothesisStatus.SUPPORTED
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
    """Reasoning over provenance-linked facts.

    Phase 3:
    - modality ladder (network → web) as first-class late-bound proposals
    - discriminating experiments when multiple open hypotheses compete
    - still never bypasses Scope / risk / approval (enforced by the loop)
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
        open_left = [
            h for h in new_hypotheses if h.status is HypothesisStatus.OPEN and h.confidence >= 0.25
        ]

        # Phase 3a: competing open hypotheses → discriminating experiment first
        if run.target and len(open_left) >= 2:
            disc_hypos, disc_props = discriminating_experiment(
                target=run.target,
                open_hypotheses=open_left,
                tried=tried,
            )
            if disc_props:
                new_hypotheses.extend(disc_hypos)
                proposals.extend(disc_props)
                return ReasoningDecision.create(
                    action=ReasoningAction.PROPOSE,
                    summary="Multiple open hypotheses compete; proposing a discriminating experiment.",
                    basis_fact_ids=tuple(node.id for node in facts[:16]),
                    new_proposals=proposals,
                    hypotheses=new_hypotheses,
                )

        # Phase 3b: modality ladder — switch capability when residual uncertainty remains
        if run.target:
            modality_props = next_modality_proposals(
                target=run.target,
                tried=tried,
                has_web_surface=_has_web_surface(facts),
                fact_count=len(facts),
            )
            if modality_props:
                # Attach a fresh open hypothesis for the modality switch when sparse
                if len(facts) < 3:
                    hypo = Hypothesis.create(
                        statement=(
                            f"Target {run.target} may still expose unobserved surfaces "
                            f"in the next research modality."
                        ),
                        confidence=0.4,
                        status=HypothesisStatus.OPEN,
                        metadata={"kind": "modality_switch"},
                    )
                    new_hypotheses.append(hypo)
                    modality_props = [
                        ActionProposal.create(
                            tool=p.tool,
                            target=p.target,
                            parameters=p.parameters,
                            rationale=p.rationale,
                            expected_info_gain=p.expected_info_gain,
                            risk=p.risk,
                            requires_approval=p.requires_approval,
                            hypothesis_id=hypo.id,
                            estimated_cost=p.estimated_cost,
                            metadata=dict(p.metadata),
                        )
                        for p in modality_props
                    ]
                proposals.extend(modality_props)

        if proposals:
            return ReasoningDecision.create(
                action=ReasoningAction.PROPOSE,
                summary="Residual uncertainty remains; advancing along the modality ladder.",
                basis_fact_ids=tuple(node.id for node in facts[:16]),
                new_proposals=proposals,
                hypotheses=new_hypotheses,
            )

        if not open_left:
            return ReasoningDecision.create(
                action=ReasoningAction.COMPLETE,
                summary="No open high-value hypotheses remain and no new modality step is justified.",
                basis_fact_ids=tuple(node.id for node in facts[:16]),
                hypotheses=new_hypotheses,
            )

        return ReasoningDecision.create(
            action=ReasoningAction.COMPLETE,
            summary=(
                "Open hypotheses remain but every safe modality step has already been tried; "
                "further progress needs a new capability or human direction."
            ),
            basis_fact_ids=tuple(node.id for node in facts[:16]),
            hypotheses=new_hypotheses,
        )
