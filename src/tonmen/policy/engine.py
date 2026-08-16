from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from tonmen.tools.base import RiskLevel, ToolRequest, ToolSpec


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
    """Genesis policy: autonomous low-risk work, approval for validation/intrusive, deny destructive."""

    def evaluate(self, spec: ToolSpec, request: ToolRequest) -> PolicyDecision:
        if request.tool.strip().lower() != spec.name.strip().lower():
            return PolicyDecision(Decision.DENY, "request/tool specification mismatch")
        if spec.risk >= RiskLevel.DESTRUCTIVE:
            return PolicyDecision(Decision.DENY, "destructive actions are disabled by default")
        if spec.risk >= RiskLevel.VALIDATION:
            return PolicyDecision(Decision.REQUIRE_APPROVAL, "higher-risk action requires approval")
        return PolicyDecision(Decision.ALLOW, "risk level is within autonomous policy")
