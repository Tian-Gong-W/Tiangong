from __future__ import annotations

import subprocess

from tonmen.agents import MissionPlanner
from tonmen.core.config import TonmenConfig
from tonmen.core.runtime import TonmenRuntime
from tonmen.jobs import JobManager
from tonmen.loop import MissionLoop
from tonmen.missions import MissionRunState, StepExecutionState
from tonmen.reasoning import ActionProposal, ReasoningAction, ReasoningDecision


def _runtime(tmp_path, monkeypatch):
    runtime = TonmenRuntime.sentinel(TonmenConfig(workspace=tmp_path, allowed_targets=("localhost",)))
    calls: list[list[str]] = []

    monkeypatch.setattr("tonmen.tools.base.shutil.which", lambda name: f"/usr/bin/{name}")

    def fake_runner(argv, **kwargs):
        calls.append(list(argv))
        return subprocess.CompletedProcess(
            argv,
            0,
            stdout="Nmap scan report for localhost\nHost is up.\n80/tcp open http\n",
            stderr="",
        )

    runtime.executor._runner = fake_runner
    runtime.jobs = JobManager(runtime.executor)
    return runtime, calls


def _proposal(*, requires_approval: bool = True, ports: str = "80") -> ActionProposal:
    return ActionProposal.create(
        tool="nmap",
        target="localhost",
        parameters={"ports": ports, "service_detection": False},
        rationale="Collect one bounded piece of evidence.",
        expected_info_gain=0.6,
        risk=3 if requires_approval else 1,
        requires_approval=requires_approval,
        estimated_cost=1,
    )


def test_dynamic_action_waits_then_resumes_exact_same_proposal(tmp_path, monkeypatch):
    runtime, calls = _runtime(tmp_path, monkeypatch)
    plan = MissionPlanner(runtime).plan("localhost")
    loop = MissionLoop(runtime)
    run = loop.coordinator.start(plan)
    for execution in run.steps:
        execution.state = StepExecutionState.SKIPPED

    proposal = _proposal()
    decision = ReasoningDecision.create(
        action=ReasoningAction.PROPOSE,
        summary="Candidate requires explicit approval.",
        new_proposals=(proposal,),
    )
    loop._record_hypotheses_and_proposals(run, decision)

    scheduled = loop._schedule_one_proposal(run, decision, approval_tokens={})

    assert scheduled == 0
    assert calls == []
    assert run.state is MissionRunState.WAITING_APPROVAL
    dynamic = [step for step in run.steps if step.metadata.get("dynamic")]
    assert len(dynamic) == 1
    waiting = dynamic[0]
    assert waiting.id == f"dynamic:{proposal.id}"
    assert waiting.state is StepExecutionState.WAITING_APPROVAL
    assert waiting.metadata["proposal_id"] == proposal.id

    grant = runtime.approvals.issue(tool=proposal.tool, target=proposal.target)
    resumed = loop.director.decide_next(
        plan,
        run,
        approval_tokens={waiting.id: grant.token},
    )

    assert resumed.action is ReasoningAction.PROPOSE
    assert len(resumed.new_proposals) == 1
    assert resumed.new_proposals[0].id == proposal.id

    scheduled = loop._schedule_one_proposal(
        run,
        resumed,
        approval_tokens={waiting.id: grant.token},
    )

    assert scheduled == 1
    assert len(calls) == 1
    dynamic = [step for step in run.steps if step.metadata.get("dynamic")]
    assert len(dynamic) == 1
    assert dynamic[0].id == waiting.id
    assert dynamic[0].state is StepExecutionState.SUCCEEDED
    assert dynamic[0].evidence_id
    assert run.state is MissionRunState.RUNNING


def test_reasoning_turn_executes_only_one_candidate_action(tmp_path, monkeypatch):
    runtime, calls = _runtime(tmp_path, monkeypatch)
    plan = MissionPlanner(runtime).plan("localhost")
    loop = MissionLoop(runtime)
    run = loop.coordinator.start(plan)

    first = _proposal(requires_approval=False, ports="80")
    second = _proposal(requires_approval=False, ports="443")
    decision = ReasoningDecision.create(
        action=ReasoningAction.PROPOSE,
        summary="Ranked action candidates.",
        new_proposals=(first, second),
    )
    loop._record_hypotheses_and_proposals(run, decision)

    scheduled = loop._schedule_one_proposal(run, decision, approval_tokens={})

    assert scheduled == 1
    assert len(calls) == 1
    assert "80" in calls[0]
    dynamic = [step for step in run.steps if step.metadata.get("dynamic")]
    assert [step.metadata.get("proposal_id") for step in dynamic] == [first.id]
