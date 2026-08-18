from __future__ import annotations

import os
from pathlib import Path

from tonmen.tools.base import CapabilityPlanningSpec, RiskLevel, ToolAdapter, ToolReadiness, ToolRequest, ToolSpec
from tonmen.tools.validation import reject_unknown_parameters, validate_web_target

_ALLOWED_SEVERITIES = {"info", "low", "medium", "high", "critical"}


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
        planning=CapabilityPlanningSpec(
            target_kinds=("host", "web"),
            requires_profile=("has_web_surface",),
            requires_capabilities=("endpoint.discover",),
            basis_fact_kinds=("intelligence.web", "intelligence.finding"),
            resolves_unknowns=("validation_coverage",),
            default_parameters={"severity": ("medium", "high", "critical"), "rate_limit": 10, "timeout": 10},
            rationale="Use bounded template validation only after endpoint coverage exists; explicit human approval remains mandatory.",
            information_gain="evidence-backed validation findings and severity evidence",
            information_gain_score=0.72,
            cost_score=0.58,
        ),
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

    def adapt_parameters(self, request: ToolRequest, context):
        complexity = max(1, min(5, int(context.get("complexity", 1))))
        parameters = dict(request.parameters)
        parameters["rate_limit"] = 6 if complexity >= 4 else 10
        parameters["timeout"] = max(5, min(20, 6 + complexity * 2))
        parameters.setdefault("severity", ("medium", "high", "critical"))
        resolved = ToolRequest(tool=request.tool, target=request.target, parameters=parameters, context=request.context)
        self.validate(resolved)
        return parameters

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
