from __future__ import annotations

import sys

from tonmen.tools.base import CapabilityPlanningSpec, RiskLevel, ToolAdapter, ToolReadiness, ToolRequest, ToolSpec
from tonmen.tools.validation import reject_unknown_parameters, validate_web_target


class CrawlerAdapter(ToolAdapter):
    spec = ToolSpec(
        name="crawler",
        category="web.discovery",
        description="Same-origin bounded HTML discovery and passive Web/session posture observation",
        risk=RiskLevel.DISCOVERY,
        capabilities=(
            "http.crawl",
            "endpoint.discover",
            "page.metadata",
            "security_headers.observe",
            "session_cookie.observe",
            "cors.observe",
        ),
        planning=CapabilityPlanningSpec(
            target_kinds=("host", "web"),
            requires_profile=("has_web_surface",),
            requires_capabilities=("http.metadata",),
            basis_fact_kinds=("intelligence.web", "intelligence.service"),
            resolves_unknowns=("same_origin_endpoint_coverage",),
            default_parameters={"max_pages": 25, "max_depth": 2, "timeout": 10},
            rationale="Expand a confirmed HTTP surface with bounded same-origin endpoint and passive posture evidence.",
            information_gain="same-origin pages, routes, page metadata and passive security posture",
            information_gain_score=0.82,
            cost_score=0.42,
        ),
    )

    def readiness(self) -> ToolReadiness:
        return ToolReadiness(
            True,
            "ready",
            f"built-in Python crawler ready: {sys.executable}",
            metadata={"python": sys.executable, "same_origin": True, "passive_session_posture": True},
        )

    def validate(self, request: ToolRequest) -> None:
        reject_unknown_parameters(request.parameters, {"max_pages", "max_depth", "timeout"})
        validate_web_target(request.target)
        max_pages = request.parameters.get("max_pages", 25)
        max_depth = request.parameters.get("max_depth", 2)
        timeout = request.parameters.get("timeout", 10)
        if not isinstance(max_pages, int) or not 1 <= max_pages <= 100:
            raise ValueError("max_pages must be an integer from 1 to 100")
        if not isinstance(max_depth, int) or not 0 <= max_depth <= 4:
            raise ValueError("max_depth must be an integer from 0 to 4")
        if not isinstance(timeout, int) or not 1 <= timeout <= 30:
            raise ValueError("timeout must be an integer from 1 to 30")

    def adapt_parameters(self, request: ToolRequest, context):
        complexity = max(1, min(5, int(context.get("complexity", 1))))
        observed_pages = max(1, int(context.get("web_url_count", 0)))
        adaptive_pages = 12 + complexity * 8 + min(24, observed_pages * 2)
        parameters = dict(request.parameters)
        parameters["max_pages"] = max(12, min(60, adaptive_pages))
        parameters["max_depth"] = max(1, min(4, 1 + complexity // 2))
        parameters["timeout"] = max(5, min(20, 6 + complexity * 2))
        resolved = ToolRequest(tool=request.tool, target=request.target, parameters=parameters, context=request.context)
        self.validate(resolved)
        return parameters

    def build_argv(self, request: ToolRequest) -> tuple[str, ...]:
        self.validate(request)
        return (
            sys.executable,
            "-m",
            "tonmen.tools.runners.crawler",
            "--url",
            str(request.target),
            "--max-pages",
            str(request.parameters.get("max_pages", 25)),
            "--max-depth",
            str(request.parameters.get("max_depth", 2)),
            "--timeout",
            str(request.parameters.get("timeout", 10)),
        )
