from __future__ import annotations

from tonmen.tools.base import RiskLevel, ToolAdapter, ToolRequest, ToolSpec
from tonmen.tools.validation import reject_unknown_parameters, validate_web_target

_ALLOWED_SEVERITIES = {"info", "low", "medium", "high", "critical"}


class NucleiAdapter(ToolAdapter):
    spec = ToolSpec(
        name="nuclei",
        category="web.validation",
        description="Template-based vulnerability validation with bounded parameters",
        risk=RiskLevel.VALIDATION,
        capabilities=("vulnerability.validate", "finding.generate"),
    )

    def validate(self, request: ToolRequest) -> None:
        reject_unknown_parameters(request.parameters, {"severity", "rate_limit", "timeout"})
        validate_web_target(request.target)
        severity = request.parameters.get("severity", ("medium", "high", "critical"))
        if isinstance(severity, str):
            values = tuple(part.strip().lower() for part in severity.split(",") if part.strip())
        elif isinstance(severity, (tuple, list)):
            values = tuple(str(part).strip().lower() for part in severity)
        else:
            raise ValueError("severity must be a string or sequence")
        if not values or any(value not in _ALLOWED_SEVERITIES for value in values):
            raise ValueError("unsupported nuclei severity")
        rate_limit = request.parameters.get("rate_limit", 25)
        timeout = request.parameters.get("timeout", 10)
        if not isinstance(rate_limit, int) or not 1 <= rate_limit <= 50:
            raise ValueError("rate_limit must be an integer from 1 to 50")
        if not isinstance(timeout, int) or not 1 <= timeout <= 30:
            raise ValueError("timeout must be an integer from 1 to 30")

    def build_argv(self, request: ToolRequest) -> tuple[str, ...]:
        self.validate(request)
        severity = request.parameters.get("severity", ("medium", "high", "critical"))
        if isinstance(severity, str):
            severity_text = ",".join(part.strip().lower() for part in severity.split(",") if part.strip())
        else:
            severity_text = ",".join(str(part).strip().lower() for part in severity)
        return (
            "nuclei",
            "-u", str(request.target),
            "-jsonl",
            "-severity", severity_text,
            "-rate-limit", str(request.parameters.get("rate_limit", 25)),
            "-timeout", str(request.parameters.get("timeout", 10)),
        )
