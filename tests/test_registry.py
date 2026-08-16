from tonmen.tools.base import RiskLevel, ToolAdapter, ToolRequest, ToolSpec
from tonmen.tools.registry import ToolRegistry


class DemoAdapter(ToolAdapter):
    spec = ToolSpec(
        name="demo",
        category="test",
        description="test adapter",
        risk=RiskLevel.DISCOVERY,
        capabilities=("test.run",),
    )

    def validate(self, request: ToolRequest) -> None:
        if request.tool != "demo":
            raise ValueError("wrong tool")

    def build_argv(self, request: ToolRequest):
        return ["demo", "--safe"]


def test_register_and_lookup():
    registry = ToolRegistry()
    adapter = DemoAdapter()
    registry.register(adapter)
    assert len(registry) == 1
    assert registry.get("DEMO") is adapter


def test_duplicate_registration_rejected():
    registry = ToolRegistry()
    registry.register(DemoAdapter())
    try:
        registry.register(DemoAdapter())
    except ValueError as exc:
        assert "already registered" in str(exc)
    else:
        raise AssertionError("duplicate tool registration should fail")
