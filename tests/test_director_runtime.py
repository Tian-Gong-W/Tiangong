from __future__ import annotations

import subprocess

from tonmen.agents import MissionPlanner
from tonmen.core.config import TonmenConfig
from tonmen.core.runtime import TonmenRuntime
from tonmen.jobs import JobManager
from tonmen.loop import LoopStopReason, MissionLoop
from tonmen.missions import StepExecution, StepExecutionState, iter_plan_executions
from tonmen.reasoning import ReasoningAction, ReasoningDecision


def _runtime(tmp_path):
    runtime = TonmenRuntime.sentinel(TonmenConfig(workspace=tmp_path, allowed_targets=("localhost",)))
    calls: list[list[str]] = []

    def fake_runner(argv, **kwargs):
        calls.append(list(argv))
        output = "Nmap scan report for localhost\nHost is up.\n" if argv[0] == "nmap" else ""
        return subprocess.CompletedProcess(argv, 0, stdout=output, stderr="")

    runtime.executor._runner = fake_runner
    runtime.jobs = JobManager(runtime.executor)
    return runtime, calls


class _CompleteDirector:
    def decide_next(self, plan, run, *, approval_tokens=None):
        return ReasoningDecision.create(
            action=ReasoningAction.COMPLETE,
            summary="Current evidence is sufficient; no action is justified.",
        )


class _OneActionThenCompleteDirector:
    def __init__(self):
        self.calls = 0

    def decide_next(self, plan, run, *, approval_tokens=None):
        self.calls += 1
        if self.calls == 1:
            return ReasoningDecision.create(
                action=ReasoningAction.CONTINUE,
                summary="Execute one compatibility action, then reassess.",
                next_step_id=plan.steps[0].id,
            )
        return ReasoningDecision.create(
            action=ReasoningAction.COMPLETE,
            summary="Stop after reassessment; remaining frozen steps are no longer justified.",
        )


def test_director_is_consulted_before_any_legacy_action(tmp_path):
    runtime, calls = _runtime(tmp_path)
    plan = MissionPlanner(runtime).plan("localhost")
    loop = MissionLoop(runtime)
    loop.director = _CompleteDirector()

    result = loop.run(plan)

    assert result.stop_reason is LoopStopReason.COMPLETE
    assert calls == []
    assert all(step.state is StepExecutionState.SKIPPED for step in result.run.steps)


def test_director_can_stop_after_one_action_without_traversing_frozen_plan(tmp_path):
    runtime, calls = _runtime(tmp_path)
    plan = MissionPlanner(runtime).plan("localhost")
    loop = MissionLoop(runtime)
    director = _OneActionThenCompleteDirector()
    loop.director = director

    result = loop.run(plan)

    assert result.stop_reason is LoopStopReason.COMPLETE
    assert director.calls == 2
    assert [call[0] for call in calls] == ["nmap"]
    assert result.run.steps[0].state is StepExecutionState.SUCCEEDED
    assert all(step.state is StepExecutionState.SKIPPED for step in result.run.steps[1:])


def test_legacy_plan_pairing_ignores_appended_dynamic_actions(tmp_path):
    runtime, _ = _runtime(tmp_path)
    plan = MissionPlanner(runtime).plan("localhost")
    run = MissionLoop(runtime).coordinator.start(plan)
    run.steps.append(
        StepExecution(
            step_id="dynamic:test",
            tool="synthetic",
            target="localhost",
            state=StepExecutionState.SUCCEEDED,
            metadata={"dynamic": True},
        )
    )

    pairs = list(iter_plan_executions(plan, run))

    assert len(pairs) == len(plan.steps)
    assert all(planned.id == execution.step_id for planned, execution in pairs)
