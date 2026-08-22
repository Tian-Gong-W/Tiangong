from __future__ import annotations

from tonmen.agents import MissionPlanner
from tonmen.core.config import TonmenConfig
from tonmen.core.runtime import TonmenRuntime
from tonmen.evidence import GraphNode
from tonmen.missions import MissionPlan, MissionRun, MissionRunState, MissionStep, StepExecution, StepExecutionState
from tonmen.reasoning import Hypothesis, HypothesisStatus, MissionDirector, ReasoningAction
from tonmen.tools import ToolRequest


def _runtime(tmp_path):
    return TonmenRuntime.sentinel(TonmenConfig(workspace=tmp_path, allowed_targets=("localhost",)))


def test_builtin_capabilities_self_describe_and_declared_defaults_validate(tmp_path):
    runtime = _runtime(tmp_path)
    for adapter in runtime.registry:
        spec = adapter.spec
        assert spec.capabilities and spec.accepts and spec.produces and spec.modalities
        assert spec.estimated_cost.effective_units > 0
        adapter.validate(ToolRequest(tool=spec.name, target="localhost", parameters=dict(spec.default_parameters)))


def test_director_ranks_capability_utility_instead_of_frozen_plan_order(tmp_path):
    runtime = _runtime(tmp_path)
    plan = MissionPlanner(runtime).plan("localhost")
    run = MissionRun.create(plan); run.state = MissionRunState.RUNNING
    assert plan.steps[0].tool == "nmap"
    decision = MissionDirector(runtime).decide_next(plan, run)
    assert decision.action is ReasoningAction.CONTINUE
    selected = next(step for step in plan.steps if step.id == decision.next_step_id)
    assert selected.tool == "httpx"
    assert decision.hypotheses
    assert "capability utility" in decision.summary


def test_dynamic_proposal_uses_adapter_contract_not_modality_specific_parameters(tmp_path):
    runtime = _runtime(tmp_path)
    nmap = runtime.registry.get("nmap").spec
    plan = MissionPlan.create("localhost", [MissionStep.create(tool="nmap", target="localhost", parameters=dict(nmap.default_parameters), risk=int(nmap.risk), requires_approval=False, rationale="compat")])
    run = MissionRun.create(plan); run.state = MissionRunState.RUNNING
    decision = MissionDirector(runtime).decide_next(plan, run)
    assert decision.action is ReasoningAction.PROPOSE
    proposal = decision.new_proposals[0]
    assert proposal.tool == "httpx"
    assert proposal.parameters == {"follow_redirects": False, "timeout": 10}
    assert "args" not in proposal.parameters and "templates" not in proposal.parameters
    assert proposal.metadata["produces"] == ["http_observation", "technology_observation"]


def test_validation_is_not_selected_while_hypothesis_is_only_open(tmp_path):
    runtime = _runtime(tmp_path)
    plan = MissionPlan.create("localhost", [])
    run = MissionRun.create(plan); run.state = MissionRunState.RUNNING
    run.steps.extend([
        StepExecution("dynamic:httpx", "httpx", "localhost", StepExecutionState.SUCCEEDED, metadata={"dynamic": True}),
        StepExecution("dynamic:nmap", "nmap", "localhost", StepExecutionState.SUCCEEDED, metadata={"dynamic": True}),
    ])
    hypothesis = Hypothesis.create(statement="A possible condition remains unconfirmed.", confidence=0.5, status=HypothesisStatus.OPEN)
    run.graph.add_node(GraphNode(id=hypothesis.id, kind="hypothesis", label=hypothesis.statement, metadata={"confidence": hypothesis.confidence, "status": hypothesis.status.value}))
    decision = MissionDirector(runtime).decide_next(plan, run)
    assert decision.action is ReasoningAction.COMPLETE
    assert not decision.new_proposals


def test_modality_ladder_is_not_part_of_public_reasoning_runtime():
    import tonmen.reasoning as reasoning
    assert "MODALITY_LADDER" not in reasoning.__all__
    assert "next_modality_proposals" not in reasoning.__all__
