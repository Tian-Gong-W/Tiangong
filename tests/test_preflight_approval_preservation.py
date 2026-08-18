from __future__ import annotations

from tonmen.agents import MissionCoordinator
from tonmen.core.config import TonmenConfig
from tonmen.core.runtime import TonmenRuntime
from tonmen.missions import MissionPlan, MissionRunState, MissionStep, StepExecutionState
from tonmen.tools import RiskLevel, ToolAdapter, ToolReadiness, ToolRequest, ToolSpec


class UnreadyValidationAdapter(ToolAdapter):
    spec = ToolSpec(
        name="unready-validation",
        category="validation.test",
        description="test-only unavailable approval-gated adapter",
        risk=RiskLevel.VALIDATION,
        preflight_readiness=True,
    )

    def readiness(self) -> ToolReadiness:
        return ToolReadiness(False, "missing_test_dependency", "test dependency unavailable")

    def validate(self, request: ToolRequest) -> None:
        if request.target != "localhost":
            raise ValueError("localhost only")

    def build_argv(self, request: ToolRequest):
        self.validate(request)
        return ("unready-validation",)


def test_preflight_failure_keeps_unconsumed_approval_grant(tmp_path):
    runtime = TonmenRuntime.sentinel(
        TonmenConfig(workspace=tmp_path, allowed_targets=("localhost",))
    )
    runtime.registry.register(UnreadyValidationAdapter())
    step = MissionStep.create(
        tool="unready-validation",
        target="localhost",
        parameters={},
        risk=int(RiskLevel.VALIDATION),
        requires_approval=True,
        rationale="test preflight approval preservation",
    )
    plan = MissionPlan.create("localhost", [step])
    coordinator = MissionCoordinator(runtime)
    run = coordinator.start(plan)
    grant = runtime.approvals.issue(tool=step.tool, target=step.target)

    coordinator.advance_once(plan, run, approval_tokens={step.id: grant.token})

    assert run.state is MissionRunState.WAITING_APPROVAL
    assert run.steps[0].state is StepExecutionState.WAITING_APPROVAL
    assert run.steps[0].metadata["preflight"]["ready"] is False
    assert runtime.approvals.validate(
        grant.token,
        ToolRequest(tool=step.tool, target=step.target),
    ) == grant
