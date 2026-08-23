from __future__ import annotations

from tonmen.agents import MissionPlanner
from tonmen.core.config import TonmenConfig
from tonmen.core.runtime import TonmenRuntime
from tonmen.missions import ActionOutcome, ActionOutcomeKind, MissionRun, record_action_outcome
from tonmen.reasoning import MissionDirector, WorldModel
from tonmen.tools import (
    CapabilityRequest,
    CostEstimate,
    RiskLevel,
    ToolAdapter,
    ToolReadiness,
    ToolRequest,
    ToolSpec,
)
from tonmen.tools.resolver import CapabilityResolver


def _runtime(tmp_path):
    return TonmenRuntime.sentinel(TonmenConfig(workspace=tmp_path, allowed_targets=("localhost",)))


class _AlternateServiceAdapter(ToolAdapter):
    spec = ToolSpec(
        name="alternate-service",
        category="network.discovery",
        description="Synthetic alternate service observer",
        risk=RiskLevel.DISCOVERY,
        capabilities=("service.observe",),
        accepts=("host",),
        produces=("service_observation",),
        modalities=("network",),
        estimated_cost=CostEstimate(wall_seconds=0.2),
        default_parameters=(),
    )

    def readiness(self):
        return ToolReadiness(True, "ready", "synthetic adapter ready")

    def validate(self, request: ToolRequest) -> None:
        if request.target != "localhost" or request.parameters:
            raise ValueError("unexpected synthetic request")

    def build_argv(self, request: ToolRequest):
        self.validate(request)
        return ("alternate-service", str(request.target))


class _NovelCheapAdapter(ToolAdapter):
    spec = ToolSpec(
        name="novel-cheap",
        category="observation.synthetic",
        description="Cheap novel modality",
        risk=RiskLevel.PASSIVE,
        capabilities=("evidence.observe",),
        accepts=("host",),
        produces=("novel_observation",),
        modalities=("text",),
        estimated_cost=CostEstimate(wall_seconds=0.01),
        default_parameters=(),
    )

    def readiness(self):
        return ToolReadiness(True, "ready", "synthetic adapter ready")

    def validate(self, request: ToolRequest) -> None:
        if request.target != "localhost" or request.parameters:
            raise ValueError("unexpected synthetic request")

    def build_argv(self, request: ToolRequest):
        self.validate(request)
        return ("novel-cheap", str(request.target))


def test_capability_request_resolves_service_evidence_without_naming_nmap(tmp_path):
    runtime = _runtime(tmp_path)
    request = CapabilityRequest.create(
        target="localhost",
        required_products=["service_observation"],
        preferred_modalities=["network"],
        max_risk=int(RiskLevel.DISCOVERY),
        require_product_match=True,
        rationale="need direct service evidence",
    )

    resolution = CapabilityResolver(runtime.registry, runtime.policy).resolve(request)

    assert resolution is not None
    assert resolution.tool == "nmap"
    assert resolution.matched_products == ("service_observation",)
    assert "nmap" not in request.as_dict().values()


def test_resolver_uses_world_capability_envelope_to_switch_adapter(tmp_path):
    runtime = _runtime(tmp_path)
    runtime.registry.register(_AlternateServiceAdapter())
    plan = MissionPlanner(runtime).plan("localhost")
    run = MissionRun.create(plan)
    record_action_outcome(
        run,
        ActionOutcome.create(
            action_id="dynamic:nmap-missing",
            proposal_id="nmap-missing",
            kind=ActionOutcomeKind.TOOL_UNAVAILABLE,
            summary="nmap unavailable in this environment",
            tool="nmap",
            target="localhost",
        ),
    )
    world = WorldModel.from_run(run, registry=runtime.registry)
    request = CapabilityRequest.create(
        target="localhost",
        required_products=["service_observation"],
        max_risk=int(RiskLevel.DISCOVERY),
        require_product_match=True,
    )

    resolution = CapabilityResolver(runtime.registry, runtime.policy).resolve(request, world=world)

    assert resolution is not None
    assert resolution.tool == "alternate-service"
    assert "nmap" in world.unavailable_capabilities


def test_exploration_request_can_choose_novel_modality_instead_of_becoming_new_ladder(tmp_path):
    runtime = _runtime(tmp_path)
    runtime.registry.register(_NovelCheapAdapter())
    request = CapabilityRequest.create(
        target="localhost",
        required_products=["service_observation", "http_observation"],
        preferred_modalities=["network", "http"],
        max_risk=int(RiskLevel.ACTIVE),
        require_product_match=False,
    )

    resolution = CapabilityResolver(runtime.registry, runtime.policy).resolve(request)

    assert resolution is not None
    assert resolution.tool == "novel-cheap"
    assert resolution.matched_products == ()


def test_director_dynamic_proposal_records_request_and_resolution_provenance(tmp_path):
    runtime = _runtime(tmp_path)
    plan = MissionPlanner(runtime).plan("localhost")
    runtime.registry.register(_NovelCheapAdapter())
    run = MissionRun.create(plan)

    decision = MissionDirector(runtime).decide_next(plan, run)

    assert decision.new_proposals
    proposal = decision.new_proposals[0]
    assert proposal.tool == "novel-cheap"
    request = proposal.metadata["capability_request"]
    resolution = proposal.metadata["capability_resolution"]
    assert request["target"] == "localhost"
    assert "service_observation" in request["required_products"]
    assert request["require_product_match"] is False
    assert resolution["tool"] == "novel-cheap"
    assert resolution["request_id"] == request["id"]
    assert proposal.metadata["adapter_late_bound"] is True
