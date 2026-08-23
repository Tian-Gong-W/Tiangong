from __future__ import annotations

from tonmen.adaptive import AdaptiveParameterResolver
from tonmen.capabilities import CapabilityCatalog
from tonmen.core.config import TonmenConfig
from tonmen.core.runtime import TonmenRuntime
from tonmen.missions import MissionPlan, MissionRun, MissionStep
from tonmen.tools import CapabilityPlanningSpec, RiskLevel, ToolAdapter, ToolRequest, ToolSpec


class RuntimePluginAdapter(ToolAdapter):
    spec = ToolSpec(
        name="runtime-plugin",
        category="test.plugin",
        description="runtime plugin for catalog bridge test",
        risk=RiskLevel.PASSIVE,
        capabilities=("plugin.observe",),
        planning=CapabilityPlanningSpec(
            target_kinds=("host", "web"),
            default_parameters={"budget": 1},
            rationale="collect bounded plugin evidence",
            information_gain="plugin evidence",
            information_gain_score=0.55,
            cost_score=0.1,
        ),
    )

    def validate(self, request: ToolRequest) -> None:
        if not request.target:
            raise ValueError("target required")
        if set(request.parameters) != {"budget"}:
            raise ValueError("budget is required")
        budget = request.parameters["budget"]
        if not isinstance(budget, int) or not 1 <= budget <= 5:
            raise ValueError("budget out of bounds")

    def adapt_parameters(self, request: ToolRequest, context):
        parameters = dict(request.parameters)
        parameters["budget"] = max(1, min(5, int(context.get("complexity", 1))))
        self.validate(ToolRequest(tool=request.tool, target=request.target, parameters=parameters))
        return parameters

    def build_argv(self, request: ToolRequest):
        self.validate(request)
        return ("runtime-plugin", "--budget", str(request.parameters["budget"]), str(request.target))


def test_runtime_plugin_parameters_survive_catalog_to_default_resolver(tmp_path):
    runtime = TonmenRuntime.sentinel(TonmenConfig(workspace=tmp_path, allowed_targets=("localhost",)))
    runtime.executor._runner = lambda argv, **kwargs: None
    runtime.registry.register(RuntimePluginAdapter())

    plan = MissionPlan.create("localhost", [])
    run = MissionRun.create(plan)
    candidate = CapabilityCatalog(runtime).evaluate(plan, run, "runtime-plugin")

    assert candidate.eligible is True
    assert candidate.parameters == {"budget": 1}

    step = MissionStep.create(
        tool=candidate.tool,
        target=candidate.target,
        parameters=candidate.parameters,
        risk=candidate.risk,
        requires_approval=candidate.requires_approval,
        rationale=candidate.rationale,
    )
    default_resolver = AdaptiveParameterResolver()

    justified, reason = default_resolver.justify(plan, run, step)
    resolved = default_resolver.resolve(plan, run, step)

    assert justified is True
    assert "CapabilityCatalog" in reason
    assert resolved == candidate.parameters
    runtime.registry.get(step.tool).validate(
        ToolRequest(tool=step.tool, target=step.target, parameters=resolved)
    )
