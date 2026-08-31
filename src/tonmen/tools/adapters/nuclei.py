from __future__ import annotations

import os
from pathlib import Path

from tonmen.tools.base import CostEstimate, RiskLevel, ToolAdapter, ToolReadiness, ToolRequest, ToolSpec
from tonmen.tools.validation import reject_unknown_parameters, validate_web_target

_ALLOWED_SEVERITIES = {"info", "low", "medium", "high", "critical"}
_DEFAULT_SEVERITIES = ("low", "medium", "high", "critical")


def _template_root() -> Path:
    configured = os.environ.get("TONMEN_NUCLEI_TEMPLATES", "").strip()
    return (Path(configured).expanduser() if configured else Path.home() / "nuclei-templates").resolve()


def _contains_templates(root: Path) -> bool:
    if not root.is_dir():
        return False
    try:
        return next(root.rglob("*.yaml"), None) is not None or next(root.rglob("*.yml"), None) is not None
    except OSError:
        return False


class NucleiAdapter(ToolAdapter):
    spec = ToolSpec(
        name="nuclei",
        category="web.validation",
        description="Template-based vulnerability validation with bounded parameters",
        risk=RiskLevel.VALIDATION,
        capabilities=("vulnerability.validate", "finding.generate"),
        accepts=("url", "host"),
        produces=("validation_observation",),
        optional_produces=("finding",),
        modalities=("http", "json"),
        estimated_cost=CostEstimate(wall_seconds=30, network_requests=12),
        replayable=True,
        isolation_profile="scoped_network",
        requires_approval=True,
        default_parameters=(("severity", _DEFAULT_SEVERITIES), ("rate_limit", 10), ("timeout", 10)),
    )

    def readiness(self) -> ToolReadiness:
        binary = super().readiness()
        if not binary.ready:
            return binary
        root = _template_root()
        if not _contains_templates(root):
            return ToolReadiness(
                False,
                "missing_templates",
                f"Nuclei binary is ready, but no YAML templates were found under {root}",
                remediation=(
                    "Run `nuclei -ut` to install/update community templates. "
                    "If templates live elsewhere, set TONMEN_NUCLEI_TEMPLATES to that directory."
                ),
                metadata={"binary": binary.metadata.get("path"), "templates_path": str(root)},
            )
        return ToolReadiness(
            True,
            "ready",
            f"binary ready: {binary.metadata.get('path')}; templates ready: {root}",
            metadata={"binary": binary.metadata.get("path"), "templates_path": str(root)},
        )

    def validate(self, request: ToolRequest) -> None:
        reject_unknown_parameters(request.parameters, {"severity", "rate_limit", "timeout"})
        validate_web_target(request.target)
        severity = request.parameters.get("severity", _DEFAULT_SEVERITIES)
        if isinstance(severity, str):
            values = tuple(part.strip().lower() for part in severity.split(",") if part.strip())
        elif isinstance(severity, (tuple, list)):
            values = tuple(str(part).strip().lower() for part in severity)
        else:
            raise ValueError("severity must be a string or sequence")
        if not values or any(value not in _ALLOWED_SEVERITIES for value in values):
            raise ValueError("unsupported nuclei severity")
        rate_limit = request.parameters.get("rate_limit", 10)
        timeout = request.parameters.get("timeout", 10)
        if not isinstance(rate_limit, int) or not 1 <= rate_limit <= 50:
            raise ValueError("rate_limit must be an integer from 1 to 50")
        if not isinstance(timeout, int) or not 1 <= timeout <= 30:
            raise ValueError("timeout must be an integer from 1 to 30")

    def build_argv(self, request: ToolRequest) -> tuple[str, ...]:
        self.validate(request)
        severity = request.parameters.get("severity", _DEFAULT_SEVERITIES)
        if isinstance(severity, str):
            severity_text = ",".join(part.strip().lower() for part in severity.split(",") if part.strip())
        else:
            severity_text = ",".join(str(part).strip().lower() for part in severity)
        return (
            "nuclei",
            "-u", str(request.target),
            "-jsonl",
            "-silent",
            "-no-mhe",
            "-severity", severity_text,
            "-rate-limit", str(request.parameters.get("rate_limit", 10)),
            "-timeout", str(request.parameters.get("timeout", 10)),
        )