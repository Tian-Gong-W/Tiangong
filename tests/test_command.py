import pytest

from tonmen.agents import MissionPlanner, MissionPlanningDenied
from tonmen.console import render_plan
from tonmen.core.config import TonmenConfig
from tonmen.core.runtime import TonmenRuntime
from tonmen.evidence import EvidenceGraph, GraphNode
from tonmen.missions import StepState
from tonmen.observations import Observation


def test_planner_builds_governed_three_step_plan(tmp_path):
    runtime = TonmenRuntime.sentinel(TonmenConfig(workspace=tmp_path, allowed_targets=("localhost",)))
    plan = MissionPlanner(runtime).plan("https://localhost")
    assert [step.tool for step in plan.steps] == ["nmap", "httpx", "nuclei"]
    assert plan.steps[0].target == "localhost"
    assert plan.steps[2].state is StepState.WAITING_APPROVAL
    assert plan.steps[2].requires_approval is True


def test_planner_rejects_out_of_scope_target(tmp_path):
    runtime = TonmenRuntime.sentinel(TonmenConfig(workspace=tmp_path, allowed_targets=("localhost",)))
    with pytest.raises(MissionPlanningDenied, match="outside"):
        MissionPlanner(runtime).plan("https://example.com")


def test_planner_does_not_execute_tools(tmp_path):
    runtime = TonmenRuntime.sentinel(TonmenConfig(workspace=tmp_path, allowed_targets=("localhost",)))
    assert not (tmp_path / "audit.jsonl").exists()
    MissionPlanner(runtime).plan("localhost")
    assert not (tmp_path / "audit.jsonl").exists()


def test_render_plan_surfaces_approval_boundary(tmp_path):
    runtime = TonmenRuntime.sentinel(TonmenConfig(workspace=tmp_path, allowed_targets=("localhost",)))
    text = render_plan(MissionPlanner(runtime).plan("localhost"))
    assert "nuclei" in text
    assert "需審批" in text


def test_observation_has_stable_provenance_fields():
    observation = Observation.create(source="httpx", target="localhost", summary="HTTP 200", evidence_id="e-1")
    assert observation.source == "httpx"
    assert observation.evidence_id == "e-1"
    assert observation.id


def test_evidence_graph_requires_existing_nodes():
    graph = EvidenceGraph()
    graph.add_node(GraphNode(id="mission-1", kind="mission", label="Mission"))
    graph.add_node(GraphNode(id="evidence-1", kind="evidence", label="HTTP evidence"))
    graph.link("mission-1", "produced", "evidence-1")
    assert graph.edges[0].relation == "produced"
    with pytest.raises(KeyError):
        graph.link("missing", "produced", "evidence-1")
