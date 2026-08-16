from __future__ import annotations

import json
import subprocess

from tonmen.agents import MissionCoordinator, MissionPlanner
from tonmen.core.config import TonmenConfig
from tonmen.core.runtime import TonmenRuntime
from tonmen.jobs import JobManager
from tonmen.missions import MissionRunState, StepExecutionState


def _runtime(tmp_path, *, returncode: int = 0):
    runtime = TonmenRuntime.sentinel(TonmenConfig(workspace=tmp_path))
    calls: list[list[str]] = []

    def fake_runner(argv, **kwargs):
        calls.append(list(argv))
        if returncode:
            return subprocess.CompletedProcess(argv, returncode, stdout="", stderr="boom\n")
        output = {
            "nmap": """Nmap scan report for localhost
Host is up.
PORT   STATE SERVICE VERSION
80/tcp open  http    nginx 1.24.0
""",
            "httpx": "https://localhost [200] [Welcome] [nginx]\n",
            "nuclei": json.dumps(
                {
                    "template-id": "demo-check",
                    "info": {"name": "Demo Exposure", "severity": "medium"},
                    "matched-at": "https://localhost/demo",
                    "type": "http",
                }
            )
            + "\n",
        }[argv[0]]
        return subprocess.CompletedProcess(argv, 0, stdout=output, stderr="")

    runtime.executor._runner = fake_runner
    runtime.jobs = JobManager(runtime.executor)
    return runtime, calls


def test_coordinator_executes_discovery_and_stops_at_approval(tmp_path):
    runtime, calls = _runtime(tmp_path)
    plan = MissionPlanner(runtime).plan("localhost")

    run = MissionCoordinator(runtime).run(plan)

    assert run.state is MissionRunState.WAITING_APPROVAL
    assert [step.state for step in run.steps] == [
        StepExecutionState.SUCCEEDED,
        StepExecutionState.SUCCEEDED,
        StepExecutionState.WAITING_APPROVAL,
    ]
    assert len(calls) == 2
    assert calls[0][0] == "nmap"
    assert calls[1][0] == "httpx"
    assert len(run.observations) == 2
    assert all(observation.evidence_id for observation in run.observations)
    assert any(node.kind == "reasoning.request_approval" for node in run.graph.nodes.values())


def test_coordinator_can_resume_with_bound_approval(tmp_path):
    runtime, calls = _runtime(tmp_path)
    plan = MissionPlanner(runtime).plan("localhost")
    coordinator = MissionCoordinator(runtime)
    run = coordinator.run(plan)
    nuclei_step = plan.steps[-1]
    grant = runtime.approvals.issue(tool=nuclei_step.tool, target=nuclei_step.target)

    resumed = coordinator.resume(plan, run, approval_tokens={nuclei_step.id: grant.token})

    assert resumed is run
    assert run.state is MissionRunState.SUCCEEDED
    assert all(step.state is StepExecutionState.SUCCEEDED for step in run.steps)
    assert len(calls) == 3
    assert calls[-1][0] == "nuclei"
    assert len(run.observations) == 3


def test_coordinator_stops_after_execution_failure(tmp_path):
    runtime, calls = _runtime(tmp_path, returncode=1)
    plan = MissionPlanner(runtime).plan("localhost")

    run = MissionCoordinator(runtime).run(plan)

    assert run.state is MissionRunState.FAILED
    assert run.steps[0].state is StepExecutionState.FAILED
    assert run.steps[1].state is StepExecutionState.PENDING
    assert len(calls) == 1
    assert run.finished_at is not None
    assert any(node.kind == "reasoning.stop" for node in run.graph.nodes.values())
