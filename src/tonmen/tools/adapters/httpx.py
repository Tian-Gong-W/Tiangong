from __future__ import annotations

from tonmen.tools.base import RiskLevel, ToolAdapter, ToolRequest, ToolSpec
from tonmen.tools.validation import reject_unknown_parameters, validate_web_target


class HttpxAdapter(ToolAdapter):
    spec = ToolSpec(
        name="httpx",
        category="web.discovery",
        description="HTTP service probing and metadata collection",
        risk=RiskLevel.DISCOVERY,
        capabilities=("http.probe", "http.metadata", "technology.detect"),
    )

    def validate(self, request: ToolRequest) -> None:
        reject_unknown_parameters(request.parameters, {"follow_redirects", "timeout"})
        validate_web_target(request.target)
        if "follow_redirects" in request.parameters and not isinstance(request.parameters["follow_redirects"], bool):
            raise ValueError("follow_redirects must be boolean")
        timeout = request.parameters.get("timeout", 10)
        if not isinstance(timeout, int) or not 1 <= timeout <= 60:
            raise ValueError("timeout must be an integer from 1 to 60")

    def build_argv(self, request: ToolRequest) -> tuple[str, ...]:
        self.validate(request)
        argv: list[str] = [
            "httpx",
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
