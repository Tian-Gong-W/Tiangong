from __future__ import annotations

from tonmen.tools.base import CostEstimate, RiskLevel, ToolAdapter, ToolRequest, ToolSpec
from tonmen.tools.validation import reject_unknown_parameters, validate_host_target, validate_ports

_COMMON_SERVICE_PORTS = (
    "21,22,25,53,80,110,111,135,139,143,443,445,465,587,993,995,"
    "1433,1521,2049,2375,3000,3306,3389,5432,5601,5672,6379,"
    "8000,8080,8081,8443,8888,9000,9090,9200,11211,27017"
)


class NmapAdapter(ToolAdapter):
    spec = ToolSpec(
        name="nmap",
        category="network.discovery",
        description="Bounded TCP connect and service discovery across common exposed services",
        risk=RiskLevel.DISCOVERY,
        capabilities=("host.scan", "port.scan", "service.detect"),
        accepts=("host",),
        produces=("host_observation", "service_observation"),
        modalities=("network",),
        estimated_cost=CostEstimate(wall_seconds=12, network_requests=40),
        replayable=True,
        isolation_profile="scoped_network",
        default_parameters=(("ports", _COMMON_SERVICE_PORTS), ("service_detection", True)),
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
