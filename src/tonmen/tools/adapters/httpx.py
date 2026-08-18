from __future__ import annotations

from tonmen.tools.base import CapabilityPlanningSpec, RiskLevel, ToolAdapter, ToolReadiness, ToolRequest, ToolSpec
from tonmen.tools.binary_identity import resolve_projectdiscovery_httpx
from tonmen.tools.validation import reject_unknown_parameters, validate_web_target


class HttpxAdapter(ToolAdapter):
    spec = ToolSpec(
        name="httpx",
        category="web.discovery",
        description="HTTP service probing and metadata collection",
        risk=RiskLevel.DISCOVERY,
        capabilities=("http.probe", "http.metadata", "technology.detect"),
        planning=CapabilityPlanningSpec(
            target_kinds=("host", "web"),
            seed_for=("web",),
            requires_profile=("web_probe_warranted",),
            basis_fact_kinds=("intelligence.service",),
            resolves_unknowns=("web_reachability_and_technology",),
            default_parameters={"follow_redirects": False, "timeout": 10},
            rationale="Resolve HTTP reachability and application metadata when Web is explicit, HTTP is observed, or service evidence remains unresolved.",
            information_gain="HTTP reachability, status, title and technology evidence",
            information_gain_score=0.88,
            cost_score=0.24,
        ),
    )

    def readiness(self) -> ToolReadiness:
        resolution = resolve_projectdiscovery_httpx()
        if resolution.ready and resolution.path:
            return ToolReadiness(
                True,
                "ready",
                resolution.detail,
                metadata={
                    "path": resolution.path,
                    "identity_verified": True,
                    "candidates": list(resolution.candidates),
                    "rejected": list(resolution.rejected),
                },
            )
        remediation = (
            "Install ProjectDiscovery httpx and ensure a compatible binary is present in PATH. "
            "If another package shadows the name, TONMEN will skip incompatible candidates and use a later compatible binary."
        )
        return ToolReadiness(
            False,
            resolution.code,
            resolution.detail,
            remediation=remediation,
            metadata={
                "identity_verified": False,
                "candidates": list(resolution.candidates),
                "rejected": list(resolution.rejected),
            },
        )

    def validate(self, request: ToolRequest) -> None:
        reject_unknown_parameters(request.parameters, {"follow_redirects", "timeout"})
        validate_web_target(request.target)
        if "follow_redirects" in request.parameters and not isinstance(request.parameters["follow_redirects"], bool):
            raise ValueError("follow_redirects must be boolean")
        timeout = request.parameters.get("timeout", 10)
        if not isinstance(timeout, int) or not 1 <= timeout <= 60:
            raise ValueError("timeout must be an integer from 1 to 60")

    def adapt_parameters(self, request: ToolRequest, context):
        complexity = max(1, min(5, int(context.get("complexity", 1))))
        parameters = dict(request.parameters)
        parameters["timeout"] = max(5, min(20, 6 + complexity * 2))
        parameters["follow_redirects"] = False
        resolved = ToolRequest(tool=request.tool, target=request.target, parameters=parameters, context=request.context)
        self.validate(resolved)
        return parameters

    def build_argv(self, request: ToolRequest) -> tuple[str, ...]:
        self.validate(request)
        resolution = resolve_projectdiscovery_httpx()
        if not resolution.ready or not resolution.path:
            raise RuntimeError(resolution.detail)
        argv: list[str] = [
            resolution.path,
            "-u", str(request.target),
            "-silent",
            "-status-code",
            "-title",
            "-tech-detect",
            "-timeout", str(request.parameters.get("timeout", 10)),
        ]
        if request.parameters.get("follow_redirects", False):
            argv.append("-follow-redirects")
        return tuple(argv)
