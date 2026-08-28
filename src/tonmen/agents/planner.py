from __future__ import annotations

import os
from typing import Any, Callable
from urllib.parse import urlparse

from tonmen.assets import build_resolved_asset_set
from tonmen.core.runtime import TonmenRuntime
from tonmen.missions import MissionPlan, MissionStep
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


class MissionPlanner:
    """Build a governed compatibility plan from registered capabilities.

    The plan is no longer the runtime heartbeat; ``MissionDirector`` chooses each
    next action. This projection remains for CLI/report compatibility and initial
    execution slots while that legacy surface is retired.

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

    @staticmethod
    def _legacy_priority(spec: CapabilitySpec) -> int:
        semantics = set(spec.capabilities)
        if "domain.enumerate" in semantics or "subdomain.discover" in semantics:
            return 5
        if "host.scan" in semantics or "port.scan" in semantics:
            return 10
        if "http.probe" in semantics:
            return 20
        if "web.crawl" in semantics or "endpoint.discover" in semantics:
            return 25
        if spec.risk >= RiskLevel.VALIDATION:
            return 30
        return 100

    @staticmethod
    def _target_for(spec: CapabilitySpec, target: str) -> str:
        if spec.accepts and "url" not in spec.accepts and "host" in spec.accepts:
            return _host_target(target)
        return target

    def plan(self, target: str) -> MissionPlan:
        if self.runtime.scope is None or not self.runtime.scope.is_allowed(target):
            raise MissionPlanningDenied("target is outside the authorized scope")

        asset_set = self.asset_resolver(target, self.runtime.scope)
        if not isinstance(asset_set, dict):
            raise MissionPlanningDenied("asset resolver returned invalid data")

        steps: list[MissionStep] = []
        host = _host_target(target)
        authorized_addresses = [
            str(item)
            for item in asset_set.get("authorized_addresses", [])
            if isinstance(item, str) and item.strip()
        ]
        eligible_direct_targets = [item for item in authorized_addresses if item != host]
        coverage_enabled = _resolved_ip_coverage_enabled()

        adapters = sorted(self.runtime.registry, key=lambda item: self._legacy_priority(item.spec))
        base_slots = max(1, len(adapters))
        max_extra_backends = max(0, 16 - base_slots)
        direct_coverage_targets = eligible_direct_targets[:max_extra_backends] if coverage_enabled else []
        deferred_due_to_bound = eligible_direct_targets[max_extra_backends:] if coverage_enabled else []

        for adapter in adapters:
            spec = adapter.spec
            parameters = dict(spec.default_parameters)
            semantics = set(spec.capabilities)
            is_network_discovery = "host.scan" in semantics or "port.scan" in semantics
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
                        "Cover an independently authorized DNS-resolved backend with this network capability; "
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

        recommended_max_executions = min(16, max(1, len(steps)))
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
                "and TONMEN_RESOLVED_IP_COVERAGE=1. The compatibility projection is bounded to the runtime execution ceiling."
            ),
        }
        return MissionPlan.create(
            target,
            steps,
            metadata={"resolved_assets": asset_set, "coverage_plan": coverage},
        )
