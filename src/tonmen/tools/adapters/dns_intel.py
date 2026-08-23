from __future__ import annotations

import sys

from tonmen.tools.base import CapabilityPlanningSpec, RiskLevel, ToolAdapter, ToolReadiness, ToolRequest, ToolSpec
from tonmen.tools.validation import reject_unknown_parameters, validate_host_target


class DnsIntelAdapter(ToolAdapter):
    spec = ToolSpec(
        name="dns-intel",
        category="network.intelligence",
        description="Bounded hostname identity and address resolution using the local resolver",
        risk=RiskLevel.DISCOVERY,
        capabilities=("dns.resolve", "address.discover"),
        planning=CapabilityPlanningSpec(
            target_kinds=("host", "web"),
            target_mode="host",
            requires_profile=("dns_resolution_needed",),
            basis_fact_kinds=("intelligence.host", "intelligence.service", "intelligence.web"),
            resolves_unknowns=("dns_identity",),
            default_parameters={},
            rationale="Resolve hostname identity and address evidence when DNS posture is still unknown.",
            information_gain="A/AAAA address identity, canonical hostname and bounded reverse identity evidence",
            information_gain_score=0.56,
            cost_score=0.08,
            include_in_baseline_envelope=False,
        ),
    )

    def readiness(self) -> ToolReadiness:
        return ToolReadiness(
            True,
            "ready",
            f"built-in Python DNS resolver ready: {sys.executable}",
            metadata={"python": sys.executable, "bounded": True},
        )

    def validate(self, request: ToolRequest) -> None:
        reject_unknown_parameters(request.parameters, set())
        validate_host_target(request.target)

    def build_argv(self, request: ToolRequest) -> tuple[str, ...]:
        self.validate(request)
        return (
            sys.executable,
            "-m",
            "tonmen.tools.runners.dns_intel",
            "--host",
            str(request.target),
        )
