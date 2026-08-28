from __future__ import annotations

from tonmen.tools.base import CostEstimate, RiskLevel, ToolAdapter, ToolRequest, ToolSpec
from tonmen.tools.validation import reject_unknown_parameters, validate_web_target


class KatanaAdapter(ToolAdapter):
    spec = ToolSpec(
        name="katana",
        category="web.discovery",
        description="Bounded HTTP crawler for URL, route and JavaScript endpoint discovery",
        risk=RiskLevel.DISCOVERY,
        capabilities=("web.crawl", "endpoint.discover", "javascript.endpoint.discover"),
        accepts=("url", "host"),
        produces=("endpoint_observation",),
        modalities=("http", "text"),
        estimated_cost=CostEstimate(wall_seconds=12, network_requests=20),
        replayable=True,
        isolation_profile="scoped_network",
        default_parameters=(("depth", 2), ("javascript", True),),
    )

    def validate(self, request: ToolRequest) -> None:
        reject_unknown_parameters(request.parameters, {"depth", "javascript"})
        validate_web_target(request.target)
        depth = request.parameters.get("depth", 2)
        if not isinstance(depth, int) or not 1 <= depth <= 4:
            raise ValueError("depth must be an integer from 1 to 4")
        if not isinstance(request.parameters.get("javascript", True), bool):
            raise ValueError("javascript must be boolean")

    def build_argv(self, request: ToolRequest) -> tuple[str, ...]:
        self.validate(request)
        argv = [
            "katana",
            "-u", str(request.target),
            "-silent",
            "-d", str(request.parameters.get("depth", 2)),
            "-kf", "robotstxt,sitemapxml",
        ]
        if request.parameters.get("javascript", True):
            argv.append("-jc")
        return tuple(argv)
