from __future__ import annotations

from tonmen.tools.base import CostEstimate, RiskLevel, ToolAdapter, ToolRequest, ToolSpec
from tonmen.tools.validation import reject_unknown_parameters, validate_host_target


class SubfinderAdapter(ToolAdapter):
    spec = ToolSpec(
        name="subfinder",
        category="domain.discovery",
        description="Passive subdomain discovery for an explicitly scoped root domain",
        risk=RiskLevel.PASSIVE,
        capabilities=("domain.enumerate", "subdomain.discover"),
        accepts=("host",),
        produces=("domain_observation",),
        modalities=("dns", "text"),
        estimated_cost=CostEstimate(wall_seconds=8, network_requests=0),
        replayable=True,
        isolation_profile="scoped_network",
        default_parameters=(),
    )

    def validate(self, request: ToolRequest) -> None:
        reject_unknown_parameters(request.parameters, set())
        target = validate_host_target(request.target)
        if target.replace(".", "").isdigit() or ":" in target:
            raise ValueError("subfinder requires a DNS hostname, not an IP literal")

    def build_argv(self, request: ToolRequest) -> tuple[str, ...]:
        self.validate(request)
        return ("subfinder", "-d", str(request.target), "-silent")
