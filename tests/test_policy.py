from tonmen.policy.engine import Decision, PolicyEngine
from tonmen.tools.base import RiskLevel, ToolRequest, ToolSpec


def spec(risk: RiskLevel) -> ToolSpec:
    return ToolSpec(name="demo", category="test", description="demo", risk=risk)


def test_low_risk_is_allowed():
    result = PolicyEngine().evaluate(spec(RiskLevel.DISCOVERY), ToolRequest(tool="demo"))
    assert result.decision is Decision.ALLOW


def test_validation_requires_approval():
    result = PolicyEngine().evaluate(spec(RiskLevel.VALIDATION), ToolRequest(tool="demo"))
    assert result.decision is Decision.REQUIRE_APPROVAL


def test_destructive_is_denied():
    result = PolicyEngine().evaluate(spec(RiskLevel.DESTRUCTIVE), ToolRequest(tool="demo"))
    assert result.decision is Decision.DENY
