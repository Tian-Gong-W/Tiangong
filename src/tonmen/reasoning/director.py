from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping
from urllib.parse import urlparse

from tonmen.core.runtime import TonmenRuntime
from tonmen.missions import MissionPlan, MissionRun, StepExecutionState, iter_plan_executions
from tonmen.policy import Decision
from tonmen.tools import CapabilitySpec, RiskLevel, ToolRequest

from .engine import MissionReasoner
from .model import ActionProposal, Hypothesis, HypothesisStatus, ReasoningAction, ReasoningDecision


@dataclass(frozen=True, slots=True)
class _CapabilityCandidate:
    spec: CapabilitySpec
    target: str
    parameters: dict
    missing_products: tuple[str, ...]
    information_gain: float
    utility: float
    requires_approval: bool


class MissionDirector:
    """Single next-action authority for a mission.

    The Director asks which registered capability can cheaply produce evidence the
    current world model does not yet contain. Concrete tool names remain adapter
    implementations; frozen plan order is only a compatibility fallback.
    """

    def __init__(self, runtime: TonmenRuntime | None = None, reasoner: MissionReasoner | None = None) -> None:
        self.runtime = runtime
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
    def _host_target(target: str) -> str:
        parsed = urlparse(target if "://" in target else f"scheme://{target}")
        return parsed.hostname or target

    @classmethod
    def _target_for(cls, spec: CapabilitySpec, target: str) -> str:
        if spec.accepts and "url" not in spec.accepts and "host" in spec.accepts:
            return cls._host_target(target)
        return target

    @staticmethod
    def _facts(run: MissionRun):
        return [node for node in run.graph.nodes.values() if node.kind.startswith("intelligence.")]

    @classmethod
    def _approval_basis(cls, run: MissionRun, spec: CapabilitySpec):
        facts = cls._facts(run)
        if "vulnerability.validate" not in set(spec.capabilities):
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

    @staticmethod
    def _initial_hypothesis(run: MissionRun) -> Hypothesis | None:
        if any(node.kind == "hypothesis" for node in run.graph.nodes.values()):
            return None
        return Hypothesis.create(
            statement=(
                f"Authorized target {run.target} may expose passive services or web surfaces "
                "that can be characterized by evidence."
            ),
            confidence=0.5,
            status=HypothesisStatus.OPEN,
            metadata={
                "kind": "bootstrap",
                "source": "mission_director",
                "evidence_need": "characterize observable target surface",
            },
        )

    @staticmethod
    def _attempted_actions(run: MissionRun) -> set[tuple[str, str]]:
        attempted: set[tuple[str, str]] = set()
        for execution in run.steps:
            if execution.state is StepExecutionState.PENDING:
                continue
            attempted.add((execution.tool.strip().lower(), execution.target))
        return attempted

    def _observed_modalities(self, run: MissionRun) -> set[str]:
        if self.runtime is None:
            return set()
        observed: set[str] = set()
        for execution in run.steps:
            if execution.state not in {StepExecutionState.SUCCEEDED, StepExecutionState.DEGRADED}:
                continue
            try:
                spec = self.runtime.registry.get(execution.tool).spec
            except KeyError:
                continue
            observed.update(spec.modalities)
        return observed

    @staticmethod
    def _observed_products(run: MissionRun) -> set[str]:
        products: set[str] = set()
        for node in run.graph.nodes.values():
            if not node.kind.startswith("intelligence."):
                continue
            kind = node.kind.removeprefix("intelligence.")
            if kind == "finding":
                products.add("finding")
            else:
                products.add(f"{kind}_observation")
        return products

    @staticmethod
    def _supported(hypotheses: tuple[Hypothesis, ...]) -> bool:
        return any(hypothesis.status is HypothesisStatus.SUPPORTED for hypothesis in hypotheses)

    @staticmethod
    def _information_gain(
        spec: CapabilitySpec,
        *,
        observed_modalities: set[str],
        observed_products: set[str],
    ) -> tuple[float, tuple[str, ...]]:
        by_risk = {
            RiskLevel.PASSIVE: 0.70,
            RiskLevel.DISCOVERY: 1.00,
            RiskLevel.ACTIVE: 0.80,
            RiskLevel.VALIDATION: 0.90,
            RiskLevel.INTRUSIVE: 0.55,
            RiskLevel.DESTRUCTIVE: 0.0,
        }
        missing_products = tuple(product for product in spec.produces if product not in observed_products)
        if spec.produces and not missing_products:
            return 0.0, ()
        novelty = (len(missing_products) / len(spec.produces)) if spec.produces else 0.5
        modality_novelty = 1.0 if spec.modalities and any(m not in observed_modalities for m in spec.modalities) else 0.0
        gain = by_risk[spec.risk] * (0.75 + (0.35 * novelty) + (0.10 * modality_novelty))
        return min(1.0, gain), missing_products

    def _rank_capabilities(
        self,
        plan: MissionPlan,
        run: MissionRun,
        hypotheses: tuple[Hypothesis, ...],
    ) -> list[_CapabilityCandidate]:
        if self.runtime is None:
            return []
        attempted = self._attempted_actions(run)
        observed_modalities = self._observed_modalities(run)
        observed_products = self._observed_products(run)
        supported = self._supported(hypotheses)
        candidates: list[_CapabilityCandidate] = []

        for adapter in self.runtime.registry:
            spec = adapter.spec
            if spec.risk >= RiskLevel.DESTRUCTIVE:
                continue
            if spec.risk >= RiskLevel.VALIDATION and not supported:
                continue
            target = self._target_for(spec, plan.target)
            if (spec.name.strip().lower(), target) in attempted:
                continue
            parameters = dict(spec.default_parameters)
            request = ToolRequest(tool=spec.name, target=target, parameters=parameters)
            try:
                adapter.validate(request)
            except ValueError:
                continue
            policy = self.runtime.policy.evaluate(spec, request)
            if policy.decision is Decision.DENY:
                continue
            gain, missing = self._information_gain(
                spec,
                observed_modalities=observed_modalities,
                observed_products=observed_products,
            )
            if gain <= 0:
                continue
            cost = spec.estimated_cost.effective_units
            approval_penalty = 1.15 if policy.decision is Decision.REQUIRE_APPROVAL or spec.requires_approval else 1.0
            candidates.append(
                _CapabilityCandidate(
                    spec=spec,
                    target=target,
                    parameters=parameters,
                    missing_products=missing,
                    information_gain=gain,
                    utility=gain / (cost * approval_penalty),
                    requires_approval=(policy.decision is Decision.REQUIRE_APPROVAL or spec.requires_approval),
                )
            )
        candidates.sort(key=lambda item: (item.utility, item.information_gain), reverse=True)
        return candidates

    @classmethod
    def _same_target_identity(cls, left: str, right: str) -> bool:
        if left == right:
            return True
        return cls._host_target(left).strip().lower() == cls._host_target(right).strip().lower()

    @classmethod
    def _matching_pending_step(cls, plan: MissionPlan, run: MissionRun, candidate: _CapabilityCandidate):
        for planned, execution in iter_plan_executions(plan, run):
            if execution.state is not StepExecutionState.PENDING:
                continue
            if planned.tool.strip().lower() != candidate.spec.name.strip().lower():
                continue
            if cls._same_target_identity(planned.target, candidate.target):
                return planned, execution
        return None

    def _candidate_decision(
        self,
        plan: MissionPlan,
        run: MissionRun,
        candidate: _CapabilityCandidate,
        hypotheses: tuple[Hypothesis, ...],
    ) -> ReasoningDecision:
        basis = tuple(node.id for node in self._facts(run)[:16])
        need = ", ".join(candidate.missing_products) or "novel evidence"
        summary = (
            f"Select capability {candidate.spec.name}: produce {need}; expected information gain "
            f"{candidate.information_gain:.2f} at cost {candidate.spec.estimated_cost.effective_units:.2f}."
        )
        match = self._matching_pending_step(plan, run, candidate)
        if match is not None:
            planned, _ = match
            return ReasoningDecision.create(
                action=ReasoningAction.CONTINUE,
                summary=summary,
                basis_fact_ids=basis,
                next_step_id=planned.id,
                hypotheses=hypotheses,
            )

        hypothesis_id = next(
            (h.id for h in hypotheses if h.status is HypothesisStatus.SUPPORTED),
            next((h.id for h in hypotheses if h.status is HypothesisStatus.OPEN), None),
        )
        proposal = ActionProposal.create(
            tool=candidate.spec.name,
            target=candidate.target,
            parameters=candidate.parameters,
            rationale=summary,
            expected_info_gain=candidate.information_gain,
            risk=int(candidate.spec.risk),
            requires_approval=candidate.requires_approval,
            hypothesis_id=hypothesis_id,
            estimated_cost=max(1, round(candidate.spec.estimated_cost.effective_units)),
            metadata={
                "capabilities": list(candidate.spec.capabilities),
                "accepts": list(candidate.spec.accepts),
                "produces": list(candidate.spec.produces),
                "modalities": list(candidate.spec.modalities),
                "missing_products": list(candidate.missing_products),
                "replayable": candidate.spec.replayable,
                "isolation_profile": candidate.spec.isolation_profile,
                "selection_utility": candidate.utility,
                "cost": {
                    "wall_seconds": candidate.spec.estimated_cost.wall_seconds,
                    "compute_units": candidate.spec.estimated_cost.compute_units,
                    "network_requests": candidate.spec.estimated_cost.network_requests,
                    "output_bytes": candidate.spec.estimated_cost.output_bytes,
                },
                "authority": "mission_director",
            },
        )
        return ReasoningDecision.create(
            action=ReasoningAction.PROPOSE,
            summary=summary,
            basis_fact_ids=basis,
            new_proposals=(proposal,),
            hypotheses=hypotheses,
        )

    def _normalize_approval(
        self,
        plan: MissionPlan,
        run: MissionRun,
        decision: ReasoningDecision,
        tokens: Mapping[str, str],
    ) -> ReasoningDecision:
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
        if pair is None or self.runtime is None:
            return decision
        planned, _ = pair
        spec = self.runtime.registry.get(planned.tool).spec
        if not planned.requires_approval and not spec.requires_approval:
            return decision
        if tokens.get(planned.id):
            return decision
        basis = self._approval_basis(run, spec)
        if spec.risk >= RiskLevel.VALIDATION and not basis:
            return ReasoningDecision.create(
                action=ReasoningAction.SKIP,
                summary="No evidence-backed surface supports the approval-gated validation action.",
                next_step_id=planned.id,
                hypotheses=decision.hypotheses,
            )
        return ReasoningDecision.create(
            action=ReasoningAction.REQUEST_APPROVAL,
            summary=f"{planned.tool} is approval-gated and requires an explicit bound grant.",
            basis_fact_ids=tuple(node.id for node in basis),
            next_step_id=planned.id,
            requires_human=True,
            hypotheses=decision.hypotheses,
        )

    def decide_next(
        self,
        plan: MissionPlan,
        run: MissionRun,
        *,
        approval_tokens: Mapping[str, str] | None = None,
    ) -> ReasoningDecision:
        tokens = approval_tokens or {}

        # Dynamic actions are first-class resumable work and are handled before any
        # compatibility-plan reasoning.
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

        base = self.reasoner.decide(plan, run)
        if base.action in {ReasoningAction.STOP, ReasoningAction.REVIEW, ReasoningAction.REQUEST_APPROVAL}:
            return self._normalize_approval(plan, run, base, tokens)

        hypotheses = list(base.hypotheses)
        initial = self._initial_hypothesis(run)
        if initial is not None:
            hypotheses.append(initial)
        hypothesis_tuple = tuple(hypotheses)

        candidates = self._rank_capabilities(plan, run, hypothesis_tuple)
        if candidates:
            decision = self._candidate_decision(plan, run, candidates[0], hypothesis_tuple)
            return self._normalize_approval(plan, run, decision, tokens)

        # Compatibility is now a fallback, not the heartbeat. If equivalent
        # evidence already exists or validation lacks evidentiary basis, retire the
        # frozen step instead of executing it merely because it was pre-written.
        if base.action is ReasoningAction.CONTINUE and base.next_step_id:
            pair = self._planned_step(plan, run, base.next_step_id)
            if pair is not None and self.runtime is not None:
                planned, _ = pair
                attempted = self._attempted_actions(run)
                if (planned.tool.strip().lower(), planned.target) in attempted:
                    return ReasoningDecision.create(
                        action=ReasoningAction.SKIP,
                        summary="Equivalent capability evidence already exists; skip the frozen compatibility action.",
                        next_step_id=planned.id,
                        hypotheses=hypothesis_tuple,
                    )
                spec = self.runtime.registry.get(planned.tool).spec
                if spec.risk >= RiskLevel.VALIDATION and not self._supported(hypothesis_tuple):
                    return ReasoningDecision.create(
                        action=ReasoningAction.SKIP,
                        summary="Validation is not justified while the current hypothesis remains unsupported.",
                        next_step_id=planned.id,
                        hypotheses=hypothesis_tuple,
                    )

        return ReasoningDecision.create(
            action=base.action,
            summary=base.summary,
            basis_fact_ids=base.basis_fact_ids,
            next_step_id=base.next_step_id,
            requires_human=base.requires_human,
            new_proposals=base.new_proposals,
            hypotheses=hypothesis_tuple,
        )
