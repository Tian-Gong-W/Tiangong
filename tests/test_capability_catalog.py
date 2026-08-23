from __future__ import annotations

import inspect

from tonmen.adaptive import AdaptiveParameterResolver
from tonmen.agents import AdaptiveMissionPlanner, MissionPlanner
from tonmen.capabilities import CapabilityCatalog
from tonmen.core.config import TonmenConfig
from tonmen.core.runtime import TonmenRuntime
from tonmen.evidence import GraphNode
from tonmen.missions import MissionPlan, MissionRun, MissionStep, StepExecutionState
from tonmen.tools import CapabilityPlanningSpec, RiskLevel, ToolAdapter, ToolRequest, ToolSpec


class _SemanticAdapter(ToolAdapter):
    def __init__(self, name: str, capabilities: tuple[str, ...]) -> None:
        self.spec = ToolSpec(
            name=name,
            category="test.semantic",
            description="test semantic capability",
            risk=RiskLevel.PASSIVE,
            capabilities=capabilities,
            planning=CapabilityPlanningSpec(
                target_kinds=("host", "web"),
                default_parameters={},
                rationale="test-only semantic provider",
                information_gain="test semantic evidence",
                information_gain_score=0.1,
                cost_score=0.1,
            ),
        )

    def validate(self, request: ToolRequest) -> None:
        if not request.target:
            raise ValueError("target required")

    def build_argv(self, request: ToolRequest):
        self.validate(request)
        return (self.spec.name, str(request.target))


class _AdaptiveSemanticAdapter(_SemanticAdapter):
    def adapt_parameters(self, request: ToolRequest, context):
        return {"budget": int(context["complexity"])}

    def validate(self, request: ToolRequest) -> None:
        super().validate(request)
        if request.parameters and set(request.parameters) != {"budget"}:
            raise ValueError("unexpected test parameter")


def _runtime(tmp_path):
    runtime = TonmenRuntime.sentinel(TonmenConfig(workspace=tmp_path, allowed_targets=("localhost",)))
    runtime.executor._runner = lambda argv, **kwargs: None
    return runtime


def _successful_plan_and_run(runtime, tool: str):
    step = MissionStep.create(
        tool=tool,
        target="localhost",
        parameters={},
        risk=int(runtime.registry.get(tool).spec.risk),
        requires_approval=False,
        rationale="test semantic prerequisite",
    )
    plan = MissionPlan.create("localhost", [step])
    run = MissionRun.create(plan)
    run.steps[0].state = StepExecutionState.SUCCEEDED
    run.graph.add_node(GraphNode(id=run.id, kind="mission", label="mission", metadata={"plan_id": plan.id}))
    run.graph.add_node(
        GraphNode(
            id="web-fact",
            kind="intelligence.web",
            label="https://localhost [200]",
            metadata={
                "source": tool,
                "target": "https://localhost",
                "confidence": 1.0,
                "severity": "info",
                "data": {"url": "https://localhost", "status_code": 200},
            },
        )
    )
    return plan, run


def test_builtin_adapters_declare_catalog_planning_metadata(tmp_path):
    runtime = _runtime(tmp_path)

    for adapter in runtime.registry:
        planning = adapter.spec.planning
        assert planning is not None, adapter.spec.name
        assert planning.rationale
        assert planning.information_gain
        assert 0.0 <= planning.information_gain_score <= 1.0
        assert 0.0 <= planning.cost_score <= 1.0


def test_seed_selection_is_declared_by_target_kind_not_tool_branch(tmp_path):
    runtime = _runtime(tmp_path)
    planner = MissionPlanner(runtime)

    assert [step.tool for step in planner.seed("localhost").steps] == ["nmap"]
    assert [step.tool for step in planner.seed("https://localhost").steps] == ["httpx"]

    seed_source = inspect.getsource(MissionPlanner.seed)
    strategy_source = inspect.getsource(AdaptiveMissionPlanner.propose)
    for name in ("nmap", "httpx", "crawler", "nuclei"):
        assert f'"{name}"' not in seed_source
        assert f'"{name}"' not in strategy_source


def test_semantic_provider_can_satisfy_crawler_prerequisite_without_httpx(tmp_path):
    runtime = _runtime(tmp_path)
    runtime.registry.register(_SemanticAdapter("alternate-http-metadata", ("http.metadata",)))
    plan, run = _successful_plan_and_run(runtime, "alternate-http-metadata")

    catalog = CapabilityCatalog(runtime)
    crawler = catalog.evaluate(plan, run, "crawler")

    assert crawler.eligible is True
    assert "http.metadata" in catalog.completed_capabilities(plan, run)
    assert crawler.requires_capabilities == ("http.metadata",)
    assert crawler.score > 0
    assert any("adds semantic capabilities" in reason for reason in crawler.reasons)


def test_validation_depends_on_endpoint_capability_not_crawler_name(tmp_path):
    runtime = _runtime(tmp_path)
    runtime.registry.register(_SemanticAdapter("alternate-endpoints", ("endpoint.discover",)))
    plan, run = _successful_plan_and_run(runtime, "alternate-endpoints")

    catalog = CapabilityCatalog(runtime)
    candidate = catalog.evaluate(plan, run, "nuclei")

    assert candidate.eligible is True
    assert candidate.requires_capabilities == ("endpoint.discover",)
    assert candidate.requires_approval is True
    assert candidate.execution_authority is False


def test_ranked_candidate_exposes_selection_and_rejection_reasons(tmp_path):
    runtime = _runtime(tmp_path)
    runtime.registry.register(_SemanticAdapter("alternate-http-metadata", ("http.metadata",)))
    plan, run = _successful_plan_and_run(runtime, "alternate-http-metadata")
    catalog = CapabilityCatalog(runtime)

    ranked = catalog.rank(plan, run)
    selected = next(item for item in ranked if item.eligible)
    queued = next(item for item in ranked if item.tool == "alternate-http-metadata")

    assert selected.tool == "crawler"
    assert selected.score > queued.score
    assert selected.reasons
    assert queued.eligible is False
    assert "already queued" in " ".join(queued.reasons)
    assert selected.audit_payload()["execution_authority"] is False


def test_parameter_resolver_dispatches_to_custom_adapter_without_tool_name_branch(tmp_path):
    runtime = _runtime(tmp_path)
    runtime.registry.register(_AdaptiveSemanticAdapter("adaptive-custom", ("custom.observe",)))
    step = MissionStep.create(
        tool="adaptive-custom",
        target="localhost",
        parameters={},
        risk=int(RiskLevel.PASSIVE),
        requires_approval=False,
        rationale="custom parameter adaptation",
    )
    plan = MissionPlan.create("localhost", [step])
    run = MissionRun.create(plan)
    resolver = AdaptiveParameterResolver(runtime.registry)

    resolved = resolver.resolve(plan, run, step)

    assert resolved == {"budget": 1}
    justify_source = inspect.getsource(AdaptiveParameterResolver.justify)
    resolve_source = inspect.getsource(AdaptiveParameterResolver.resolve)
    for name in ("nmap", "httpx", "crawler", "nuclei"):
        assert f'"{name}"' not in justify_source
        assert f'"{name}"' not in resolve_source
