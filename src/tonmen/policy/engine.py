from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from tonmen.tools.base import RiskLevel, ToolRequest, ToolSpec

from .scope import TargetScope


class Decision(str, Enum):
    ALLOW = "allow"
    REQUIRE_APPROVAL = "require_approval"
    DENY = "deny"


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    decision: Decision
    reason: str

    @property
    def allowed(self) -> bool:
        return self.decision is Decision.ALLOW


class PolicyEngine:
    """Scope first; then risk policy. Destructive capability remains disabled."""

    def __init__(self, scope: TargetScope | None = None) -> None:
        self.scope = scope

    def evaluate(self, spec: ToolSpec, request: ToolRequest) -> PolicyDecision:
        if request.tool.strip().lower() != spec.name.strip().lower():
            return PolicyDecision(Decision.DENY, "request/tool specification mismatch")
        if self.scope is not None and request.target is not None and not self.scope.is_allowed(request.target):
            return PolicyDecision(Decision.DENY, "target is outside the authorized scope")
        if spec.risk >= RiskLevel.DESTRUCTIVE:
            return PolicyDecision(Decision.DENY, "destructive actions are disabled by default")
        if spec.risk >= RiskLevel.VALIDATION:
            return PolicyDecision(Decision.REQUIRE_APPROVAL, "higher-risk action requires approval")
        return PolicyDecision(Decision.ALLOW, "risk level is within autonomous policy")
