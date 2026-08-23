from __future__ import annotations

from tonmen.tools.base import CapabilityPlanningSpec, RiskLevel, ToolAdapter, ToolRequest, ToolSpec
from tonmen.tools.validation import reject_unknown_parameters, validate_host_target, validate_ports


class NmapAdapter(ToolAdapter):
    spec = ToolSpec(
        name="nmap",
        category="network.discovery",
        description="Conservative TCP connect and service discovery",
        risk=RiskLevel.DISCOVERY,
        capabilities=("host.scan", "port.scan", "service.detect"),
        planning=CapabilityPlanningSpec(
            target_kinds=("host",),
            seed_for=("host",),
            target_mode="host",
            basis_fact_kinds=(),
            resolves_unknowns=("network_surface",),
            default_parameters={"ports": "80,443", "service_detection": False},
            rationale="Establish a minimal TCP reachability view without assuming an application protocol.",
            information_gain="host reachability, open ports and service-family evidence",
            information_gain_score=0.78,
            cost_score=0.28,
        ),
        preflight_readiness=True,
    )

    def validate(self, request: ToolRequest) -> None:
        reject_unknown_parameters(request.parameters, {"ports", "service_detection", "skip_host_discovery"})
        validate_host_target(request.target)
        if "ports" in request.parameters:
            validate_ports(str(request.parameters["ports"]))
        for key in ("service_detection", "skip_host_discovery"):
            if key in request.parameters and not isinstance(request.parameters[key], bool):
                raise ValueError(f"{key} must be boolean")

    def build_argv(self, request: ToolRequest) -> tuple[str, ...]:
        self.validate(request)
        argv: list[str] = ["nmap", "-sT"]
        if request.parameters.get("service_detection", True):
            argv.append("-sV")
        if request.parameters.get("skip_host_discovery", False):
            argv.append("-Pn")
        ports = request.parameters.get("ports")
        if ports:
            argv.extend(["-p", str(ports)])
        argv.append(str(request.target))
        return tuple(argv)
