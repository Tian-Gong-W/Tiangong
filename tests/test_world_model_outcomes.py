from __future__ import annotations

import subprocess

from tonmen.agents import MissionPlanner
from tonmen.core.config import TonmenConfig
from tonmen.core.runtime import TonmenRuntime
from tonmen.evidence import GraphNode
from tonmen.jobs import JobManager
from tonmen.loop import MissionLoop, MissionLoopPolicy
from tonmen.missions import (
    ActionOutcome,
    ActionOutcomeKind,
    MissionPlan,
    MissionRun,
    MissionRunState,
    record_action_outcome,
)
from tonmen.reasoning import Hypothesis, HypothesisStatus, MissionReasoner, WorldModel
from tonmen.tools import CostEstimate, RiskLevel, ToolAdapter, ToolReadiness, ToolRequest, ToolSpec


def _runtime(tmp_path):
    return TonmenRuntime.sentinel(TonmenConfig(workspace=tmp_path, allowed_targets=("localhost",)))


class _UnavailableObserver(ToolAdapter):
    spec = ToolSpec(
        name="unavailable-observer",
        category="observation.synthetic",
        description="Unavailable cheap observer",
        risk=RiskLevel.PASSIVE,
        capabilities=("evidence.observe",),
        accepts=("host",),
        produces=("banner_observation",),
        modalities=("text",),
        estimated_cost=CostEstimate(wall_seconds=0.05),
        default_parameters=(),
    )

    def readiness(self):
        return ToolReadiness(False, "missing_binary", "synthetic observer is missing")

    def validate(self, request: ToolRequest) -> None:
        if request.target != "localhost" or request.parameters:
            raise ValueError("unexpected synthetic request")

    def build_argv(self, request: ToolRequest):
        self.validate(request)
        return ("unavailable-observer", str(request.target))


class _AlternateObserver(ToolAdapter):
    spec = ToolSpec(
        name="alternate-observer",
        category="observation.synthetic",
        description="Fallback evidence observer",
        risk=RiskLevel.PASSIVE,
        capabilities=("evidence.observe",),
        accepts=("host",),
        produces=("banner_observation",),
        modalities=("text",),
        estimated_cost=CostEstimate(wall_seconds=0.10),
        default_parameters=(),
    )

    def readiness(self):
        return ToolReadiness(True, "ready", "synthetic observer ready")

    def validate(self, request: ToolRequest) -> None:
        if request.target != "localhost" or request.parameters:
            raise ValueError("unexpected synthetic request")

    def build_argv(self, request: ToolRequest):
        self.validate(request)
        return ("alternate-observer", str(request.target))


def test_environmental_outcome_does_not_change_hypothesis_belief(tmp_path):
    plan = MissionPlan.create("localhost", [])
    run = MissionRun.create(plan)
    run.state = MissionRunState.RUNNING
    hypothesis = Hypothesis.create(
        statement="A condition may exist.",
        confidence=0.73,
        status=HypothesisStatus.OPEN,
        metadata={"evidence_need": "obtain an independent observation"},
    )
    run.graph.add_node(
        GraphNode(
            id=hypothesis.id,
            kind="hypothesis",
            label=hypothesis.statement,
            metadata={
                "status": hypothesis.status.value,
                "confidence": hypothesis.confidence,
                "evidence_need": "obtain an independent observation",
            },
        )
    )
    outcome = record_action_outcome(
        run,
        ActionOutcome.create(
            action_id="dynamic:missing",
            proposal_id="missing",
            kind=ActionOutcomeKind.TOOL_UNAVAILABLE,
            summary="binary missing",
            tool="missing-tool",
            target="localhost",
        ),
    )

    world = WorldModel.from_run(run)
    decision = MissionReasoner().decide(plan, run)

    assert outcome.environmental is True
    assert outcome.may_revise_belief is False
    assert world.environmental_outcomes[0].kind is ActionOutcomeKind.TOOL_UNAVAILABLE
    assert world.unavailable_capabilities == ("missing-tool",)
    refreshed = next(item for item in decision.hypotheses if item.id == hypothesis.id)
    assert refreshed.status is HypothesisStatus.OPEN
    assert refreshed.confidence == hypothesis.confidence


def test_world_model_normalizes_evidence_products_and_open_needs(tmp_path):
    plan = MissionPlan.create("localhost", [])
    run = MissionRun.create(plan)
    hypothesis = Hypothesis.create(
        statement="Characterize the target surface.",
        metadata={
            "evidence_need": "characterize network and HTTP behavior",
            "required_products": ["service_observation", "http_observation"],
            "preferred_modalities": ["network", "http"],
        },
    )
    run.graph.add_node(
        GraphNode(
            id=hypothesis.id,
            kind="hypothesis",
            label=hypothesis.statement,
            metadata={
                "status": "open",
                "confidence": 0.5,
                "evidence_need": "characterize network and HTTP behavior",
                "required_products": ["service_observation", "http_observation"],
                "preferred_modalities": ["network", "http"],
            },
        )
    )
    run.graph.add_node(GraphNode(id="fact-web", kind="intelligence.web", label="HTTP 200", metadata={}))

    world = WorldModel.from_run(run)

    assert "http_observation" in world.observed_products
    assert "technology_observation" in world.observed_products
    assert world.evidence_needs[0].missing_products == ("service_observation",)
    assert world.missing_products() == ("service_observation",)


def test_missing_capability_outcome_causes_director_to_choose_alternative(tmp_path):
    runtime = _runtime(tmp_path)
    plan = MissionPlanner(runtime).plan("localhost")
    runtime.registry.register(_UnavailableObserver())
    runtime.registry.register(_AlternateObserver())
    calls: list[str] = []

    def fake_runner(argv, **kwargs):
        calls.append(argv[0])
        return subprocess.CompletedProcess(argv, 0, stdout="opaque observation\n", stderr="")

    runtime.executor._runner = fake_runner
    runtime.jobs = JobManager(runtime.executor)
    loop = MissionLoop(runtime, MissionLoopPolicy(max_iterations=5, max_executions=1, max_repeat_decisions=4))

    result = loop.run(plan)
    world = WorldModel.from_run(result.run, registry=runtime.registry)
    kinds = [item.kind for item in world.action_outcomes]

    assert ActionOutcomeKind.TOOL_UNAVAILABLE in kinds
    assert "unavailable-observer" in world.unavailable_capabilities
    assert "alternate-observer" in calls
    assert "unavailable-observer" not in calls
    unavailable = next(item for item in world.action_outcomes if item.kind is ActionOutcomeKind.TOOL_UNAVAILABLE)
    assert unavailable.may_revise_belief is False


def test_success_without_parsed_facts_is_insufficient_evidence_not_success(tmp_path):
    runtime = _runtime(tmp_path)
    plan = MissionPlanner(runtime).plan("localhost")
    runtime.registry.register(_AlternateObserver())

    def fake_runner(argv, **kwargs):
        return subprocess.CompletedProcess(argv, 0, stdout="opaque observation\n", stderr="")

    runtime.executor._runner = fake_runner
    runtime.jobs = JobManager(runtime.executor)
    result = MissionLoop(runtime, MissionLoopPolicy(max_iterations=3, max_executions=1)).run(plan)
    world = WorldModel.from_run(result.run, registry=runtime.registry)

    outcome = next(item for item in world.action_outcomes if item.tool == "alternate-observer")
    assert outcome.kind is ActionOutcomeKind.INSUFFICIENT_EVIDENCE
    assert outcome.evidence_bearing is True
    assert outcome.fact_ids == ()
