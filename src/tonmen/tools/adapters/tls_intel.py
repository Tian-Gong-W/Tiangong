from __future__ import annotations

import sys
from typing import Any, Mapping

from tonmen.tools.base import CapabilityPlanningSpec, RiskLevel, ToolAdapter, ToolReadiness, ToolRequest, ToolSpec
from tonmen.tools.validation import reject_unknown_parameters, validate_host_target

_COMMON_TLS_PORTS = (443, 8443, 9443, 465, 993, 995)


class TlsIntelAdapter(ToolAdapter):
    spec = ToolSpec(
        name="tls-intel",
        category="network.intelligence",
        description="Bounded TLS handshake and certificate metadata inspection",
        risk=RiskLevel.DISCOVERY,
        capabilities=("tls.handshake", "certificate.inspect"),
        planning=CapabilityPlanningSpec(
            target_kinds=("host", "web"),
            target_mode="host",
            requires_profile=("tls_probe_warranted",),
            basis_fact_kinds=("intelligence.service", "intelligence.web", "intelligence.dns"),
            resolves_unknowns=("tls_posture",),
            default_parameters={"port": 443, "timeout": 8},
            rationale="Inspect TLS protocol and certificate identity only when target evidence warrants a TLS branch.",
            information_gain="TLS version/cipher plus certificate subject, issuer, SAN, validity and fingerprint evidence",
            information_gain_score=0.66,
            cost_score=0.16,
            include_in_baseline_envelope=False,
        ),
    )

    def readiness(self) -> ToolReadiness:
        return ToolReadiness(
            True,
            "ready",
            f"built-in Python TLS inspector ready: {sys.executable}",
            metadata={"python": sys.executable, "certificate_values_only": True},
        )

    def validate(self, request: ToolRequest) -> None:
        reject_unknown_parameters(request.parameters, {"port", "timeout"})
        validate_host_target(request.target)
        port = request.parameters.get("port", 443)
        timeout = request.parameters.get("timeout", 8)
        if not isinstance(port, int) or not 1 <= port <= 65535:
            raise ValueError("port must be an integer from 1 to 65535")
        if not isinstance(timeout, int) or not 1 <= timeout <= 20:
            raise ValueError("timeout must be an integer from 1 to 20")

    def adapt_parameters(self, request: ToolRequest, context: Mapping[str, Any]) -> Mapping[str, Any]:
        self.validate(request)
        parameters = dict(request.parameters)
        ports = context.get("ports", ())
        if isinstance(ports, (list, tuple)):
            observed = {int(value) for value in ports if isinstance(value, int) or str(value).isdigit()}
            for port in _COMMON_TLS_PORTS:
                if port in observed:
                    parameters["port"] = port
                    break
        complexity = int(context.get("complexity", 1) or 1)
        parameters["timeout"] = max(5, min(15, 6 + complexity))
        self.validate(ToolRequest(tool=request.tool, target=request.target, parameters=parameters))
        return parameters

    def build_argv(self, request: ToolRequest) -> tuple[str, ...]:
        self.validate(request)
        return (
            sys.executable,
            "-m",
            "tonmen.tools.runners.tls_intel",
            "--host",
            str(request.target),
            "--port",
            str(request.parameters.get("port", 443)),
            "--timeout",
            str(request.parameters.get("timeout", 8)),
        )
