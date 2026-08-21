from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping
from urllib.parse import urlparse

from tonmen.assets import build_resolved_asset_set
from tonmen.core.runtime import TonmenRuntime
from tonmen.hypotheses import EvidenceRequirement, Hypothesis, HypothesisStatus
from tonmen.missions import ActionProposal, MissionPlan, MissionStep
from tonmen.policy import Decision, TargetScope
from tonmen.tools import CapabilitySpec, RiskLevel, ToolRequest


class MissionPlanningDenied(RuntimeError):
    pass


def _host_target(target: str) -> str:
    parsed = urlparse(target if "://" in target else f"scheme://{target}")
    if not parsed.hostname:
        raise MissionPlanningDenied("target has no hostname")
    return parsed.hostname


def _resolved_ip_coverage_enabled() -> bool:
    return (os.getenv("TONMEN_RESOLVED_IP_COVERAGE") or "").strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True, slots=True)
class AdaptivePlanningState:
    target: str
    hypotheses: tuple[Hypothesis, ...]
    attempted_capabilities: tuple[str, ...] = ()
    observed_modalities: tuple[str, ...] = ()
    remaining_executions: int = 16

    def __post_init__(self) -> None:
        if self.remaining_executions < 0:
            raise ValueError("remaining_executions cannot be negative")


@dataclass(frozen=True, slots=True)
class BootstrapResult:
    initial_hypotheses: tuple[Hypothesis, ...]
    initial_actions: tuple[ActionProposal, ...]
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class PlannerDecision:
    candidates: tuple[ActionProposal, ...]
    explanation: str


class MissionPlanner:
    """Build governed plans and adaptive research proposals.

    ``plan`` remains the compatibility API for the existing fixed-step MissionLoop.
    New orchestration should call ``bootstrap`` once, then ``decide_next`` after
    every evidence reconciliation. Proposals never bypass Scope, Policy or Approval.

    DNS resolution never grants execution authority. Direct resolved-IP fanout is
    explicit and bounded: TONMEN_RESOLVED_IP_COVERAGE=1 must be set, every concrete
    IP must already be independently allowed by TargetScope, and one Mission never
    expands beyond the existing 16-execution loop ceiling.
    """

    def __init__(
        self,
        runtime: TonmenRuntime,
        *,
        asset_resolver: Callable[[str, TargetScope], dict[str, Any]] | None = None,
    ) -> None:
        self.runtime = runtime
        self.asset_resolver = asset_resolver or (lambda target, scope: build_resolved_asset_set(target, scope))

    def _resolve_assets(self, target: str) -> dict[str, Any]:
        if self.runtime.scope is None or not self.runtime.scope.is_allowed(target):
            raise MissionPlanningDenied("target is outside the authorized scope")
        asset_set = self.asset_resolver(target, self.runtime.scope)
        if not isinstance(asset_set, dict):
            raise MissionPlanningDenied("asset resolver returned invalid data")
        return asset_set

    @staticmethod
    def _target_for(spec: CapabilitySpec, target: str) -> str:
        if spec.accepts and "url" not in spec.accepts and "host" in spec.accepts:
            return _host_target(target)
        return target

    @staticmethod
    def _legacy_priority(spec: CapabilitySpec) -> int:
        semantics = set(spec.capabilities)
        if "port.scan" in semantics or "host.scan" in semantics:
            return 10
        if "http.probe" in semantics:
            return 20
        if spec.risk >= RiskLevel.VALIDATION or "vulnerability.validate" in semantics:
            return 30
        return 100

    @staticmethod
    def _information_gain(
        spec: CapabilitySpec,
        *,
        observed_modalities: tuple[str, ...],
        supported_hypothesis: bool,
    ) -> float:
        if spec.risk >= RiskLevel.VALIDATION and not supported_hypothesis:
            return 0.0
        by_risk = {
            RiskLevel.PASSIVE: 0.7,
            RiskLevel.DISCOVERY: 1.0,
            RiskLevel.ACTIVE: 0.8,
            RiskLevel.VALIDATION: 0.9,
            RiskLevel.INTRUSIVE: 0.6,
            RiskLevel.DESTRUCTIVE: 0.0,
        }
        value = by_risk[spec.risk]
        observed = set(observed_modalities)
        if spec.modalities and any(modality not in observed for modality in spec.modalities):
            value *= 1.2
        return min(value, 1.5)

    def _candidate_actions(self, state: AdaptivePlanningState) -> list[ActionProposal]:
        supported = any(
            hypothesis.status in {HypothesisStatus.SUPPORTED, HypothesisStatus.CONFIRMED}
            for hypothesis in state.hypotheses
        )
        attempted = {name.strip().lower() for name in state.attempted_capabilities}
        hypothesis_ids = tuple(
            hypothesis.id for hypothesis in state.hypotheses if hypothesis.status is not HypothesisStatus.REJECTED
        )
        requirements = tuple(
            requirement.description
            for hypothesis in state.hypotheses
            if hypothesis.status is not HypothesisStatus.REJECTED
            for requirement in hypothesis.evidence_requirements
        )
        candidates: list[ActionProposal] = []
        for adapter in self.runtime.registry:
            spec = adapter.spec
            if spec.name.strip().lower() in attempted:
                continue
            information_gain = self._information_gain(
                spec,
                observed_modalities=state.observed_modalities,
                supported_hypothesis=supported,
            )
            if information_gain <= 0:
                continue
            action_target = self._target_for(spec, state.target)
            parameters = dict(spec.default_parameters)
            request = ToolRequest(tool=spec.name, target=action_target, parameters=parameters)
            adapter.validate(request)
            decision = self.runtime.policy.evaluate(spec, request)
            if decision.decision is Decision.DENY:
                continue
            candidates.append(
                ActionProposal.create(
                    capability=spec.name,
                    target=action_target,
                    parameters=parameters,
                    hypothesis_ids=hypothesis_ids,
                    expected_information_gain=information_gain,
                    relevance=max((hypothesis.relevance for hypothesis in state.hypotheses), default=1.0),
                    estimated_cost=spec.estimated_cost,
                    risk=int(spec.risk),
                    replayable=spec.replayable,
                    requires_approval=decision.decision is Decision.REQUIRE_APPROVAL or spec.requires_approval,
                    evidence_requirements=requirements,
                    rationale=(
                        f"Use {spec.description} because its {', '.join(spec.modalities) or 'declared'} "
                        "evidence can reduce current mission uncertainty."
                    ),
                )
            )
        candidates.sort(key=lambda action: action.utility_score, reverse=True)
        return candidates[: state.remaining_executions]

    def bootstrap(self, target: str) -> BootstrapResult:
        """Create the minimum initial world model instead of a complete future script."""
        asset_set = self._resolve_assets(target)
        host = _host_target(target)
        hypothesis = Hypothesis.create(
            f"The authorized target {host} exposes observable network or web behavior that can be characterized.",
            scope_entities=(target, host),
            evidence_requirements=(
                EvidenceRequirement(
                    "Direct observation of an exposed service or HTTP behavior.",
                    required_modalities=("network", "http"),
                ),
            ),
            confidence=0.5,
            relevance=1.0,
            impact_prior=0.5,
        )
        state = AdaptivePlanningState(target=target, hypotheses=(hypothesis,))
        decision = self.decide_next(state)
        initial_actions = tuple(
            action
            for action in decision.candidates
            if not action.requires_approval and action.risk <= int(RiskLevel.DISCOVERY)
        )[:2]
        return BootstrapResult(
            initial_hypotheses=(hypothesis,),
            initial_actions=initial_actions,
            metadata={"resolved_assets": asset_set},
        )

    def decide_next(self, state: AdaptivePlanningState) -> PlannerDecision:
        """Propose new actions from current knowledge, not from a frozen step list."""
        self._resolve_assets(state.target)
        if state.remaining_executions == 0:
            return PlannerDecision((), "Execution budget is exhausted; no new action can be proposed.")
        candidates = tuple(self._candidate_actions(state))
        if candidates:
            return PlannerDecision(
                candidates,
                "Ranked allowed, untried capabilities by expected information gain, relevance and cost.",
            )
        return PlannerDecision(
            (),
            "No allowed untried capability can currently reduce uncertainty; converge or request review.",
        )

    def plan(self, target: str) -> MissionPlan:
        """Compatibility facade for the current fixed-step MissionLoop."""
        asset_set = self._resolve_assets(target)
        steps: list[MissionStep] = []
        host = _host_target(target)
        authorized_addresses = [
            str(item) for item in asset_set.get("authorized_addresses", []) if isinstance(item, str) and item.strip()
        ]
        eligible_direct_targets = [item for item in authorized_addresses if item != host]
        coverage_enabled = _resolved_ip_coverage_enabled()
        max_extra_backends = 13
        direct_coverage_targets = eligible_direct_targets[:max_extra_backends] if coverage_enabled else []
        deferred_due_to_bound = eligible_direct_targets[max_extra_backends:] if coverage_enabled else []

        for adapter in sorted(self.runtime.registry, key=lambda item: self._legacy_priority(item.spec)):
            spec = adapter.spec
            parameters = dict(spec.default_parameters)
            is_network_discovery = "port.scan" in spec.capabilities or "host.scan" in spec.capabilities
            targets = [host, *direct_coverage_targets] if is_network_discovery else [self._target_for(spec, target)]
            seen_targets: set[str] = set()
            for step_target in targets:
                if step_target in seen_targets:
                    continue
                seen_targets.add(step_target)
                request = ToolRequest(tool=spec.name, target=step_target, parameters=parameters)
                adapter.validate(request)
                decision = self.runtime.policy.evaluate(spec, request)
                if decision.decision is Decision.DENY:
                    continue
                requires_approval = decision.decision is Decision.REQUIRE_APPROVAL or spec.requires_approval
                rationale = spec.description
                if is_network_discovery and step_target != host:
                    rationale = (
                        "Cover an independently authorized DNS-resolved backend; "
                        "DNS resolution itself did not grant Scope."
                    )
                steps.append(
                    MissionStep.create(
                        tool=spec.name,
                        target=step_target,
                        parameters=parameters,
                        risk=int(spec.risk),
                        requires_approval=requires_approval,
                        rationale=rationale,
                    )
                )

        recommended_max_executions = min(16, max(3, len(steps)))
        coverage = {
            "primary_hostname": host,
            "web_target": target,
            "resolved_ip_coverage_enabled": coverage_enabled,
            "eligible_direct_nmap_targets": eligible_direct_targets,
            "direct_nmap_targets": direct_coverage_targets,
            "deferred_due_to_execution_bound": deferred_due_to_bound,
            "recommended_max_executions": recommended_max_executions,
            "needs_scope": list(asset_set.get("needs_scope", [])),
            "web_backend_fanout": False,
            "note": (
                "DNS answers are observations only. Direct resolved-IP network coverage requires both independent IP/CIDR Scope "
                "and TONMEN_RESOLVED_IP_COVERAGE=1. Fanout is bounded so the generated Mission stays within 16 executions. "
                "HTTP capabilities stay on the hostname to preserve Host/SNI routing."
            ),
        }
        return MissionPlan.create(
            target,
            steps,
            metadata={"resolved_assets": asset_set, "coverage_plan": coverage},
        )
