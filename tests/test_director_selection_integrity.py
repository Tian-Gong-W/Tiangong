from __future__ import annotations

from tonmen.agents import MissionPlanner
from tonmen.core.config import TonmenConfig
from tonmen.core.runtime import TonmenRuntime
from tonmen.missions import MissionRun, MissionRunState
from tonmen.reasoning import MissionDirector, ReasoningAction
from tonmen.tools import CostEstimate, RiskLevel, ToolAdapter, ToolRequest, ToolSpec


class _LaterButCheaperAdapter(ToolAdapter):
    spec = ToolSpec(
        name="later-cheap-observer",
        category="observation.synthetic",
        description="Cheaper evidence capability deliberately kept outside compatibility planning",
        risk=RiskLevel.PASSIVE,
        capabilities=("evidence.observe",),
        accepts=("host",),
        produces=("banner_observation",),
        modalities=("text",),
        estimated_cost=CostEstimate(wall_seconds=0.1),
        default_parameters=(),
    )

    def validate(self, request: ToolRequest) -> None:
        if request.target != "localhost" or request.parameters:
            raise ValueError("unexpected test request")

    def build_argv(self, request: ToolRequest):
        self.validate(request)
        return ("later-cheap-observer", str(request.target))


def test_supplemental_capability_stays_out_of_frozen_plan_and_is_late_bound(tmp_path):
    runtime = TonmenRuntime.sentinel(TonmenConfig(workspace=tmp_path, allowed_targets=("localhost",)))
    runtime.registry.register(_LaterButCheaperAdapter())
    plan = MissionPlanner(runtime).plan("localhost")
    run = MissionRun.create(plan)
    run.state = MissionRunState.RUNNING

    assert [step.tool for step in plan.steps] == ["nmap", "httpx", "nuclei"]
    assert all(step.tool != "later-cheap-observer" for step in plan.steps)

    decision = MissionDirector(runtime).decide_next(plan, run)

    assert decision.action is ReasoningAction.PROPOSE
    assert decision.next_step_id is None
    assert decision.new_proposals[0].tool == "later-cheap-observer"