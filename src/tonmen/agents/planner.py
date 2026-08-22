from __future__ import annotations

import os
from typing import Any, Callable
from urllib.parse import urlparse

from tonmen.assets import build_resolved_asset_set
from tonmen.core.runtime import TonmenRuntime
from tonmen.missions import MissionPlan, MissionStep
from tonmen.policy import Decision, TargetScope
from tonmen.research import (
    ActionProposal,
    AdaptiveMissionState,
    BootstrapResult,
    EvidenceRequirement,
    Hypothesis,
    PlannerDecision,
)
from tonmen.tools import CostEstimate, RiskLevel, ToolRequest


class MissionPlanningDenied(RuntimeError):
    pass


def _host_target(target: str) -> str:
    parsed = urlparse(target if "://" in target else f"scheme://{target}")
    if not parsed.hostname:
        raise MissionPlanningDenied("target has no hostname")
    return parsed.hostname


def _resolved_ip_coverage_enabled() -> bool:
    return (os.getenv("TONMEN_RESOLVED_IP_COVERAGE") or "").strip().lower() in {"1", "true", "yes", "on"}


def _default_parameters(tool: str) -> dict[str, Any]:
    """Conservative adapter defaults, independent from planner ordering."""
    return {
        "nmap": {"ports": "80,443", "service_detection": False},
        "httpx": {"follow_redirects": False, "timeout": 10},
        "nuclei": {"severity": ("medium", "high", "critical"), "rate_limit": 10, "timeout": 10},
    }.get(tool, {})


class MissionPlanner:
    """Plan governed security research from current state instead of a fixed script.

    ``bootstrap`` and ``decide_next`` are the adaptive interfaces. They create the
    smallest useful initial experiment and then re-plan from evidence/action state.
    ``plan`` remains as a legacy compatibility facade for the current coordinator,
    Chronicle and CLI while those components migrate to the ActionLedger model.

    DNS resolution never grants execution authority. Direct resolved-IP fanout is
    explicit and bounded: TONMEN_RESOLVED_IP_COVERAGE=1 must be set and every
    concrete IP must already be independently allowed by TargetScope.
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

    def _adaptive_candidates(
        self,
        target: str,
        *,
        asset_set: dict[str, Any],
        hypothesis_ids: tuple[str, ...],
        state: AdaptiveMissionState | None,
    ) -> list[ActionProposal]:
        host = _host_target(target)
        attempted = state.attempted_signatures if state is not None else set()
        has_evidence = bool(state and state.evidence_ids)
        proposals: list[ActionProposal] = []

        authorized_addresses = [
            str(item)
            for item in asset_set.get("authorized_addresses", [])
            if isinstance(item, str) and item.strip() and str(item) != host
        ]
        direct_targets = authorized_addresses[:13] if _resolved_ip_coverage_enabled() else []

        for adapter in self.runtime.registry:
            capability = adapter.capability

            # Validation is evidence-driven. Do not spend higher-risk budget before
            # an earlier observation has produced evidence to validate.
            if capability.risk >= RiskLevel.VALIDATION and not has_evidence:
                continue

            targets = [target]
            if any(name.startswith(("host.", "port.", "service.")) for name in capability.capabilities):
                targets = [host]
                if _resolved_ip_coverage_enabled() and "host.scan" in capability.capabilities:
                    targets.extend(direct_targets)

            for candidate_target in targets:
                parameters = _default_parameters(capability.name)
                request = ToolRequest(tool=capability.name, target=candidate_target, parameters=parameters)
                try:
                    adapter.validate(request)
                except ValueError:
                    continue

                policy = self.runtime.policy.evaluate(adapter.spec, request)
                if policy.decision is Decision.DENY:
                    continue

                information_gain = max(0.15, 1.0 - (0.12 * int(capability.risk)))
                if "://" in target and "http" in capability.category.lower():
                    information_gain += 0.25
                if candidate_target != target and candidate_target != host:
                    information_gain *= 0.75

                cost = CostEstimate(
                    wall_seconds=max(1.0, capability.cost.wall_seconds + (0.5 * int(capability.risk))),
                    compute_units=capability.cost.compute_units,
                    network_requests=max(capability.cost.network_requests, 1),
                    output_bytes=capability.cost.output_bytes,
                )
                rationale = (
                    f"Use {capability.name} because its capabilities "
                    f"{', '.join(capability.capabilities) or capability.category} can reduce current mission uncertainty."
                )
                if candidate_target != target and candidate_target != host:
                    rationale = (
                        "Observe an independently authorized DNS-resolved backend; DNS resolution itself did not grant Scope."
                    )

                proposal = ActionProposal.create(
                    capability=capability.name,
                    target=candidate_target,
                    parameters=parameters,
                    hypothesis_ids=hypothesis_ids,
                    expected_information_gain=information_gain,
                    relevance=1.0,
                    estimated_cost=cost,
                    risk=capability.risk,
                    replayable=capability.replayable,
                    requires_approval=policy.decision is Decision.REQUIRE_APPROVAL,
                    rationale=rationale,
                )
                if proposal.signature not in attempted:
                    proposals.append(proposal)

        proposals.sort(key=lambda item: item.utility, reverse=True)
        return proposals

    def bootstrap(self, target: str) -> BootstrapResult:
        """Create only the minimum initial research action, not a full future script."""
        asset_set = self._resolve_assets(target)
        hypothesis = Hypothesis.create(
            "Determine the target's observable attack surface and use evidence to choose the next experiment.",
            evidence_requirements=(
                EvidenceRequirement(
                    description="At least one direct governed observation of the authorized target.",
                    minimum_independent_sources=1,
                ),
            ),
            metadata={"phase": "bootstrap"},
        )
        candidates = self._adaptive_candidates(
            target,
            asset_set=asset_set,
            hypothesis_ids=(hypothesis.id,),
            state=None,
        )
        initial_actions = tuple(candidates[:1])
        return BootstrapResult(
            initial_hypotheses=(hypothesis,),
            initial_actions=initial_actions,
            metadata={
                "resolved_assets": asset_set,
                "planner_mode": "adaptive",
                "principle": "goals/evidence/constraints/capabilities, not a fixed script",
            },
        )

    def create_state(self, target: str) -> AdaptiveMissionState:
        bootstrap = self.bootstrap(target)
        return AdaptiveMissionState.create(
            target,
            bootstrap.initial_hypotheses,
            metadata={**dict(bootstrap.metadata), "bootstrap_action_ids": [item.id for item in bootstrap.initial_actions]},
        )

    def decide_next(self, state: AdaptiveMissionState) -> PlannerDecision:
        """Re-plan from current mission state and generate previously nonexistent actions."""
        if state.converged:
            return PlannerDecision(candidates=(), explanation="mission is already converged")

        asset_set = state.metadata.get("resolved_assets")
        if not isinstance(asset_set, dict):
            asset_set = self._resolve_assets(state.target)

        open_hypotheses = tuple(
            hypothesis.id
            for hypothesis in state.hypotheses.values()
            if hypothesis.status.value in {"open", "supported"}
        )
        if not open_hypotheses:
            return PlannerDecision(candidates=(), explanation="no open or supported hypotheses remain")

        candidates = self._adaptive_candidates(
            state.target,
            asset_set=asset_set,
            hypothesis_ids=open_hypotheses,
            state=state,
        )
        if not candidates:
            return PlannerDecision(
                candidates=(),
                explanation="no non-duplicate governed action can reduce current uncertainty",
            )
        return PlannerDecision(
            candidates=tuple(candidates),
            explanation=(
                "Candidates were regenerated from current hypotheses, prior action signatures, Scope, Policy and estimated "
                "information gain; no fixed next-step ID was required."
            ),
        )

    def plan(self, target: str) -> MissionPlan:
        """Legacy fixed-plan facade retained during migration to the adaptive Director."""
        asset_set = self._resolve_assets(target)

        defaults = {
            "nmap": {"ports": "80,443", "service_detection": False},
            "httpx": {"follow_redirects": False, "timeout": 10},
            "nuclei": {"severity": ("medium", "high", "critical"), "rate_limit": 10, "timeout": 10},
        }
        rationales = {
            "nmap": "Establish a minimal TCP reachability view on common web ports without version probing.",
            "httpx": "Collect HTTP status, title and technology metadata while preserving hostname/SNI semantics.",
            "nuclei": "Validate higher-confidence web findings only after explicit approval.",
        }
        order = {"nmap": 10, "httpx": 20, "nuclei": 30}
        steps: list[MissionStep] = []
        host = _host_target(target)
        authorized_addresses = [
            str(item)
            for item in asset_set.get("authorized_addresses", [])
            if isinstance(item, str) and item.strip()
        ]
        eligible_direct_targets = [item for item in authorized_addresses if item != host]
        coverage_enabled = _resolved_ip_coverage_enabled()

        max_extra_backends = 13
        direct_coverage_targets = eligible_direct_targets[:max_extra_backends] if coverage_enabled else []
        deferred_due_to_bound = eligible_direct_targets[max_extra_backends:] if coverage_enabled else []

        for adapter in sorted(self.runtime.registry, key=lambda item: order.get(item.spec.name, 100)):
            parameters = defaults.get(adapter.spec.name, {})
            targets = [host, *direct_coverage_targets] if adapter.spec.name == "nmap" else [target]

            seen_targets: set[str] = set()
            for step_target in targets:
                if step_target in seen_targets:
                    continue
                seen_targets.add(step_target)
                request = ToolRequest(tool=adapter.spec.name, target=step_target, parameters=parameters)
                adapter.validate(request)
                decision = self.runtime.policy.evaluate(adapter.spec, request)
                if decision.decision is Decision.DENY:
                    continue
                requires_approval = decision.decision is Decision.REQUIRE_APPROVAL
                rationale = rationales.get(adapter.spec.name, adapter.spec.description)
                if adapter.spec.name == "nmap" and step_target != host:
                    rationale = (
                        "Cover an independently authorized DNS-resolved backend on common web ports; "
                        "DNS resolution itself did not grant Scope."
                    )
                steps.append(
                    MissionStep.create(
                        tool=adapter.spec.name,
                        target=step_target,
                        parameters=parameters,
                        risk=int(adapter.spec.risk),
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
                "DNS answers are observations only. Direct resolved-IP Nmap coverage requires both independent IP/CIDR Scope "
                "and TONMEN_RESOLVED_IP_COVERAGE=1. Fanout is bounded so the generated Mission stays within 16 executions. "
                "HTTPx/Nuclei stay on the hostname to preserve Host/SNI routing."
            ),
        }
        return MissionPlan.create(
            target,
            steps,
            metadata={"resolved_assets": asset_set, "coverage_plan": coverage, "planner_mode": "legacy"},
        )
