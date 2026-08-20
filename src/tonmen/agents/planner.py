from __future__ import annotations

import os
from typing import Any, Callable
from urllib.parse import urlparse

from tonmen.assets import build_resolved_asset_set
from tonmen.core.runtime import TonmenRuntime
from tonmen.missions import MissionPlan, MissionStep
from tonmen.policy import Decision, TargetScope
from tonmen.tools import ToolRequest


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
    """Build governed plans from capabilities plus passive asset observations.

    DNS resolution never grants execution authority. Direct resolved-IP fanout is
    also explicit: TONMEN_RESOLVED_IP_COVERAGE=1 must be set, and every concrete IP
    must already be independently allowed by TargetScope.
    """

    def __init__(
        self,
        runtime: TonmenRuntime,
        *,
        asset_resolver: Callable[[str, TargetScope], dict[str, Any]] | None = None,
    ) -> None:
        self.runtime = runtime
        self.asset_resolver = asset_resolver or (lambda target, scope: build_resolved_asset_set(target, scope))

    def plan(self, target: str) -> MissionPlan:
        if self.runtime.scope is None or not self.runtime.scope.is_allowed(target):
            raise MissionPlanningDenied("target is outside the authorized scope")

        asset_set = self.asset_resolver(target, self.runtime.scope)
        if not isinstance(asset_set, dict):
            raise MissionPlanningDenied("asset resolver returned invalid data")

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
        direct_coverage_targets = eligible_direct_targets if coverage_enabled else []

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

        coverage = {
            "primary_hostname": host,
            "web_target": target,
            "resolved_ip_coverage_enabled": coverage_enabled,
            "eligible_direct_nmap_targets": eligible_direct_targets,
            "direct_nmap_targets": direct_coverage_targets,
            "needs_scope": list(asset_set.get("needs_scope", [])),
            "web_backend_fanout": False,
            "note": (
                "DNS answers are observations only. Direct resolved-IP Nmap coverage requires both independent IP/CIDR Scope "
                "and TONMEN_RESOLVED_IP_COVERAGE=1. HTTPx/Nuclei stay on the hostname to preserve Host/SNI routing."
            ),
        }
        return MissionPlan.create(
            target,
            steps,
            metadata={"resolved_assets": asset_set, "coverage_plan": coverage},
        )
