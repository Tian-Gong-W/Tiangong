from __future__ import annotations

import sys
from typing import Any, Mapping
from urllib.parse import urlparse

from tonmen.tools.base import CapabilityPlanningSpec, RiskLevel, ToolAdapter, ToolReadiness, ToolRequest, ToolSpec
from tonmen.tools.validation import reject_unknown_parameters, validate_web_target


class ApiIntelAdapter(ToolAdapter):
    spec = ToolSpec(
        name="api-intel",
        category="web.intelligence",
        description="Bounded same-origin static JavaScript/API surface intelligence",
        risk=RiskLevel.DISCOVERY,
        capabilities=("api.surface.observe", "javascript.endpoint.extract", "openapi.hint.observe"),
        planning=CapabilityPlanningSpec(
            target_kinds=("host", "web"),
            requires_profile=("has_web_surface",),
            requires_capabilities=("http.metadata",),
            basis_fact_kinds=("intelligence.web",),
            resolves_unknowns=("client_api_surface",),
            default_parameters={"max_scripts": 12, "max_bytes": 262_144, "timeout": 8},
            rationale="Inspect bounded same-origin JavaScript text for API/OpenAPI/GraphQL surface evidence without executing scripts.",
            information_gain="same-origin JavaScript assets, API endpoint strings and API technology hints",
            information_gain_score=0.80,
            cost_score=0.28,
            include_in_baseline_envelope=False,
        ),
    )

    def readiness(self) -> ToolReadiness:
        return ToolReadiness(
            True,
            "ready",
            f"built-in Python API intelligence runner ready: {sys.executable}",
            metadata={
                "python": sys.executable,
                "same_origin": True,
                "javascript_execution": False,
                "form_submission": False,
            },
        )

    @staticmethod
    def _host(value: str) -> str:
        parsed = urlparse(value if "://" in value else f"https://{value}")
        return (parsed.hostname or "").lower()

    @staticmethod
    def _bounded_entry_url(target: str, context: Mapping[str, Any]) -> str:
        if "://" in target:
            return target
        ports = context.get("ports", ())
        observed = {
            int(value)
            for value in ports
            if isinstance(value, int) or (isinstance(value, str) and value.isdigit())
        } if isinstance(ports, (list, tuple)) else set()
        if 443 in observed:
            return f"https://{target}"
        if 80 in observed:
            return f"http://{target}"
        for port in (8443, 9443):
            if port in observed:
                return f"https://{target}:{port}"
        for port in (8080, 8000, 8888):
            if port in observed:
                return f"http://{target}:{port}"
        return f"https://{target}"

    def validate(self, request: ToolRequest) -> None:
        reject_unknown_parameters(request.parameters, {"url", "max_scripts", "max_bytes", "timeout"})
        target = validate_web_target(request.target)
        url = str(request.parameters.get("url") or target)
        validate_web_target(url)
        if self._host(url) != self._host(target):
            raise ValueError("api-intel URL must stay on the target hostname")
        max_scripts = request.parameters.get("max_scripts", 12)
        max_bytes = request.parameters.get("max_bytes", 262_144)
        timeout = request.parameters.get("timeout", 8)
        if not isinstance(max_scripts, int) or not 1 <= max_scripts <= 16:
            raise ValueError("max_scripts must be an integer from 1 to 16")
        if not isinstance(max_bytes, int) or not 32_768 <= max_bytes <= 524_288:
            raise ValueError("max_bytes must be an integer from 32768 to 524288")
        if not isinstance(timeout, int) or not 1 <= timeout <= 20:
            raise ValueError("timeout must be an integer from 1 to 20")

    def adapt_parameters(self, request: ToolRequest, context: Mapping[str, Any]) -> Mapping[str, Any]:
        parameters = dict(request.parameters)
        target = str(request.target)
        parameters["url"] = self._bounded_entry_url(target, context)
        complexity = max(1, min(5, int(context.get("complexity", 1) or 1)))
        parameters["max_scripts"] = max(4, min(16, 6 + complexity * 2))
        parameters["max_bytes"] = max(65_536, min(524_288, 131_072 + complexity * 65_536))
        parameters["timeout"] = max(5, min(15, 6 + complexity))
        resolved = ToolRequest(tool=request.tool, target=request.target, parameters=parameters, context=request.context)
        self.validate(resolved)
        return parameters

    def build_argv(self, request: ToolRequest) -> tuple[str, ...]:
        self.validate(request)
        url = str(request.parameters.get("url") or request.target)
        return (
            sys.executable,
            "-m",
            "tonmen.tools.runners.api_intel",
            "--url",
            url,
            "--max-scripts",
            str(request.parameters.get("max_scripts", 12)),
            "--max-bytes",
            str(request.parameters.get("max_bytes", 262_144)),
            "--timeout",
            str(request.parameters.get("timeout", 8)),
        )
