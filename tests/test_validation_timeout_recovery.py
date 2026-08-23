from __future__ import annotations

import subprocess

from tonmen.agents import MissionCoordinator
from tonmen.core.config import TonmenConfig
from tonmen.core.runtime import TonmenRuntime
from tonmen.jobs import JobManager
from tonmen.missions import MissionPlan, MissionRunState, MissionStep, StepExecutionState
from tonmen.tools import RiskLevel, ToolAdapter, ToolRequest, ToolSpec


class ValidationDemoAdapter(ToolAdapter):
    spec = ToolSpec(
        name="validation-demo",
        category="validation.demo",
        description="test-only approval-gated validation adapter",
        risk=RiskLevel.VALIDATION,
        execution_timeout_seconds=600,
    )

    def validate(self, request: ToolRequest) -> None:
        if request.target != "localhost":
            raise ValueError("localhost only")

    def build_argv(self, request: ToolRequest):
        self.validate(request)
        return ("validation-demo", "--target", str(request.target))


def test_approval_gated_timeout_returns_to_waiting_approval_and_can_retry(tmp_path):
    runtime = TonmenRuntime.sentinel(
        TonmenConfig(workspace=tmp_path, allowed_targets=("localhost",))
    )
    runtime.registry.register(ValidationDemoAdapter())
    calls = 0

    def fake_runner(argv, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise subprocess.TimeoutExpired(
                cmd=argv,
                timeout=kwargs["timeout"],
                output="partial validation output\n",
                stderr="",
            )
        return subprocess.CompletedProcess(argv, 0, stdout="validation complete\n", stderr="")

    runtime.executor._runner = fake_runner
    runtime.jobs = JobManager(runtime.executor)
    step = MissionStep.create(
        tool="validation-demo",
        target="localhost",
        parameters={},
        risk=int(RiskLevel.VALIDATION),
        requires_approval=True,
        rationale="test approval timeout recovery",
    )
    plan = MissionPlan.create("localhost", [step])
    coordinator = MissionCoordinator(runtime)
    run = coordinator.start(plan)

    first_grant = runtime.approvals.issue(tool="validation-demo", target="localhost")
    coordinator.advance_once(plan, run, approval_tokens={step.id: first_grant.token})

    assert run.state is MissionRunState.WAITING_APPROVAL
    assert run.steps[0].state is StepExecutionState.WAITING_APPROVAL
    assert run.steps[0].metadata["timed_out"] is True
    assert run.steps[0].metadata["retry_requires_fresh_approval"] is True
    assert run.evidence[-1].exit_code == 124
    assert runtime.approvals.validate(first_grant.token, ToolRequest(tool="validation-demo", target="localhost")) is None

    second_grant = runtime.approvals.issue(tool="validation-demo", target="localhost")
    coordinator.advance_once(plan, run, approval_tokens={step.id: second_grant.token})

    assert calls == 2
    assert run.steps[0].state is StepExecutionState.SUCCEEDED
    assert run.state in {MissionRunState.RUNNING, MissionRunState.SUCCEEDED}
