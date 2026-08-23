from __future__ import annotations

from tonmen.agents import MissionPlanner
from tonmen.core.config import TonmenConfig
from tonmen.core.runtime import TonmenRuntime
from tonmen.evidence import GraphNode
from tonmen.missions import MissionPlan, MissionRun, MissionRunState, StepExecution, StepExecutionState
from tonmen.reasoning import Hypothesis, HypothesisStatus, MissionDirector, ReasoningAction
from tonmen.tools import CostEstimate, RiskLevel, ToolAdapter, ToolRequest, ToolSpec


def _runtime(tmp_path):
    return TonmenRuntime.sentinel(TonmenConfig(workspace=tmp_path, allowed_targets=("localhost",)))


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


def test_director_can_choose_cheaper_capability_outside_frozen_plan_order(tmp_path):
    runtime = _runtime(tmp_path)
    plan = MissionPlanner(runtime).plan("localhost")
    runtime.registry.register(_CheapObservationAdapter())
    run = MissionRun.create(plan)
    run.state = MissionRunState.RUNNING

    assert plan.steps[0].tool == "nmap"
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
    selected = next(step for step in plan.steps if step.id == first.next_step_id)
    assert selected.tool == "nmap"

    run.steps[0].state = StepExecutionState.SUCCEEDED
    second = MissionDirector(runtime).decide_next(plan, run)
    selected = next(step for step in plan.steps if step.id == second.next_step_id)
    assert selected.tool == "httpx"


def test_validation_is_not_selected_while_hypothesis_is_only_open(tmp_path):
    runtime = _runtime(tmp_path)
    plan = MissionPlan.create("localhost", [])
    run = MissionRun.create(plan)
    run.state = MissionRunState.RUNNING
    run.steps.extend(
        [
            StepExecution("dynamic:httpx", "httpx", "localhost", StepExecutionState.SUCCEEDED, metadata={"dynamic": True}),
            StepExecution("dynamic:nmap", "nmap", "localhost", StepExecutionState.SUCCEEDED, metadata={"dynamic": True}),
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

    assert decision.action is ReasoningAction.COMPLETE
    assert not decision.new_proposals


def test_fixed_modality_ladder_is_not_part_of_public_reasoning_runtime():
    import tonmen.reasoning as reasoning

    assert "MODALITY_LADDER" not in reasoning.__all__
    assert "next_modality_proposals" not in reasoning.__all__
