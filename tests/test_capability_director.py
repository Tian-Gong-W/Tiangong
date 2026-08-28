from __future__ import annotations

from tonmen.agents import MissionPlanner
from tonmen.core.config import TonmenConfig
from tonmen.core.runtime import TonmenRuntime
from tonmen.evidence import GraphNode
from tonmen.missions import MissionPlan, MissionRun, MissionRunState, StepExecution, StepExecutionState
from tonmen.reasoning import Hypothesis, HypothesisStatus, MissionDirector, ReasoningAction
from tonmen.tools import CostEstimate, RiskLevel, ToolAdapter, ToolRequest, ToolSpec


def _runtime(tmp_path, allowed_targets=("localhost",)):
    return TonmenRuntime.sentinel(TonmenConfig(workspace=tmp_path, allowed_targets=allowed_targets))


class _CheapObservationAdapter(ToolAdapter):
    spec = ToolSpec(
        name="cheap-observer",
        category="observation.synthetic",
        description="Cheap independent observation for Director ranking tests",
        risk=RiskLevel.PASSIVE,
        capabilities=("evidence.observe",),
        accepts=("host",),
        produces=("banner_observation",),
        modalities=("text",),
        estimated_cost=CostEstimate(wall_seconds=0.1),
        replayable=True,
        default_parameters=(),
    )

    def validate(self, request: ToolRequest) -> None:
        if request.target != "localhost":
            raise ValueError("test adapter only accepts localhost")
        if request.parameters:
            raise ValueError("test adapter has no parameters")

    def build_argv(self, request: ToolRequest):
        self.validate(request)
        return ("cheap-observer", str(request.target))


def test_builtin_capabilities_self_describe_and_declared_defaults_validate(tmp_path):
    runtime = _runtime(tmp_path)
    for adapter in runtime.registry:
        spec = adapter.spec
        assert spec.capabilities
        assert spec.accepts
        assert spec.produces
        assert spec.modalities
        assert spec.estimated_cost.effective_units > 0
        adapter.validate(ToolRequest(tool=spec.name, target="localhost", parameters=dict(spec.default_parameters)))


def test_extended_discovery_expands_registry_without_rewriting_frozen_plan(tmp_path, monkeypatch):
    monkeypatch.setenv("TONMEN_EXTENDED_DISCOVERY", "1")
    runtime = _runtime(tmp_path)
    registry_tools = {adapter.spec.name for adapter in runtime.registry}

    assert {"nmap", "httpx", "nuclei", "subfinder", "katana"}.issubset(registry_tools)

    plan = MissionPlanner(runtime).plan("localhost")
    assert [step.tool for step in plan.steps] == ["nmap", "httpx", "nuclei"]


def test_director_can_choose_cheaper_capability_outside_frozen_plan_order(tmp_path):
    runtime = _runtime(tmp_path)
    plan = MissionPlanner(runtime).plan("localhost")
    runtime.registry.register(_CheapObservationAdapter())
    run = MissionRun.create(plan)
    run.state = MissionRunState.RUNNING

    assert all(step.tool != "cheap-observer" for step in plan.steps)

    decision = MissionDirector(runtime).decide_next(plan, run)

    assert decision.action is ReasoningAction.PROPOSE
    assert decision.new_proposals[0].tool == "cheap-observer"
    assert decision.new_proposals[0].metadata["missing_products"] == ["banner_observation"]
    assert decision.hypotheses
    assert "expected information gain" in decision.summary


def test_builtin_director_progression_is_cost_and_evidence_ranked(tmp_path):
    runtime = _runtime(tmp_path)
    plan = MissionPlanner(runtime).plan("localhost")
    run = MissionRun.create(plan)
    run.state = MissionRunState.RUNNING

    first = MissionDirector(runtime).decide_next(plan, run)
    selected_first = next(step for step in plan.steps if step.id == first.next_step_id)
    assert selected_first.tool == "nmap"

    execution = next(item for item in run.steps if item.step_id == selected_first.id)
    execution.state = StepExecutionState.SUCCEEDED
    _add_service_fact(run, "localhost", 80, "http")

    second = MissionDirector(runtime).decide_next(plan, run)
    selected_second = next(step for step in plan.steps if step.id == second.next_step_id)
    assert selected_second.tool == "httpx"


def _add_domain_fact(run: MissionRun, host: str) -> None:
    run.graph.add_node(
        GraphNode(
            id=f"domain:{host}",
            kind="intelligence.domain",
            label=f"Subdomain observed: {host}",
            metadata={"target": host, "data": {"host": host}, "evidence_id": "e-subfinder"},
        )
    )


def _add_service_fact(run: MissionRun, host: str, port: int, service: str) -> None:
    run.graph.add_node(
        GraphNode(
            id=f"service:{host}:{port}",
            kind="intelligence.service",
            label=f"{port}/tcp open {service}",
            metadata={
                "target": host,
                "data": {"port": port, "protocol": "tcp", "service": service, "scanned_address": host},
                "evidence_id": "e-nmap",
            },
        )
    )


def test_discovered_subdomain_becomes_candidate_only_when_scope_covers_it(tmp_path):
    wildcard_runtime = _runtime(tmp_path / "wild", ("example.test", "*.example.test"))
    plan = MissionPlan.create("example.test", [])
    run = MissionRun.create(plan)
    run.state = MissionRunState.RUNNING
    _add_domain_fact(run, "api.example.test")

    wildcard_candidates = MissionDirector(wildcard_runtime)._rank_capabilities(plan, run, ())
    assert any(item.spec.name == "httpx" and item.target == "api.example.test" for item in wildcard_candidates)
    assert any(item.spec.name == "nmap" and item.target == "api.example.test" for item in wildcard_candidates)

    exact_runtime = _runtime(tmp_path / "exact", ("example.test",))
    exact_candidates = MissionDirector(exact_runtime)._rank_capabilities(plan, run, ())
    assert not any(item.target == "api.example.test" for item in exact_candidates)


def test_web_service_facts_create_explicit_http_origins(tmp_path):
    runtime = _runtime(tmp_path)
    plan = MissionPlan.create("localhost", [])
    run = MissionRun.create(plan)
    run.state = MissionRunState.RUNNING
    _add_service_fact(run, "localhost", 8080, "http-proxy")
    _add_service_fact(run, "localhost", 8443, "ssl/http")

    candidates = MissionDirector(runtime)._rank_capabilities(plan, run, ())
    httpx_targets = {item.target for item in candidates if item.spec.name == "httpx"}

    assert "http://localhost:8080" in httpx_targets
    assert "https://localhost:8443" in httpx_targets


def test_attempted_web_origin_does_not_suppress_another_port(tmp_path):
    runtime = _runtime(tmp_path)
    plan = MissionPlan.create("localhost", [])
    run = MissionRun.create(plan)
    run.state = MissionRunState.RUNNING
    _add_service_fact(run, "localhost", 8080, "http")
    _add_service_fact(run, "localhost", 8443, "ssl/http")
    run.steps.append(
        StepExecution(
            "dynamic:httpx:8080",
            "httpx",
            "http://localhost:8080",
            StepExecutionState.SUCCEEDED,
            metadata={"dynamic": True},
        )
    )

    candidates = MissionDirector(runtime)._rank_capabilities(plan, run, ())
    httpx_targets = {item.target for item in candidates if item.spec.name == "httpx"}

    assert "http://localhost:8080" not in httpx_targets
    assert "https://localhost:8443" in httpx_targets


def test_unresolved_hypothesis_without_executable_capability_is_not_false_completion(tmp_path):
    runtime = _runtime(tmp_path)
    plan = MissionPlan.create("localhost", [])
    run = MissionRun.create(plan)
    run.state = MissionRunState.RUNNING
    run.steps.extend(
        [
            StepExecution("dynamic:httpx", "httpx", "localhost", StepExecutionState.SUCCEEDED, metadata={"dynamic": True}),
            StepExecution("dynamic:nmap", "nmap", "localhost", StepExecutionState.SUCCEEDED, metadata={"dynamic": True}),
            StepExecution("dynamic:subfinder", "subfinder", "localhost", StepExecutionState.SUCCEEDED, metadata={"dynamic": True}),
            StepExecution("dynamic:katana", "katana", "localhost", StepExecutionState.SUCCEEDED, metadata={"dynamic": True}),
        ]
    )
    hypothesis = Hypothesis.create(
        statement="A possible condition remains unconfirmed.",
        confidence=0.5,
        status=HypothesisStatus.OPEN,
    )
    run.graph.add_node(
        GraphNode(
            id=hypothesis.id,
            kind="hypothesis",
            label=hypothesis.statement,
            metadata={"confidence": hypothesis.confidence, "status": hypothesis.status.value},
        )
    )

    decision = MissionDirector(runtime).decide_next(plan, run)

    assert decision.action is ReasoningAction.NO_ACTION
    assert not decision.new_proposals
    assert "unresolved" in decision.summary


def test_fixed_modality_ladder_is_not_part_of_public_reasoning_runtime():
    import tonmen.reasoning as reasoning

    assert "MODALITY_LADDER" not in reasoning.__all__
    assert "next_modality_proposals" not in reasoning.__all__