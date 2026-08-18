from __future__ import annotations

import json
import subprocess

from tonmen.agents import MissionCoordinator, MissionPlanner
from tonmen.core.config import TonmenConfig
from tonmen.core.runtime import TonmenRuntime
from tonmen.jobs import JobManager
from tonmen.missions import MissionRunState, StepExecutionState


def _tool_name(argv) -> str:
    if argv and argv[0] in {"nmap", "httpx", "nuclei"}:
        return argv[0]
    if len(argv) >= 3 and argv[1:3] == ["-m", "tonmen.tools.runners.crawler"]:
        return "crawler"
    return str(argv[0]) if argv else "unknown"


def _runtime(tmp_path, *, returncode: int = 0):
    runtime = TonmenRuntime.sentinel(TonmenConfig(workspace=tmp_path))
    calls: list[list[str]] = []

    def fake_runner(argv, **kwargs):
        calls.append(list(argv))
        if returncode:
            return subprocess.CompletedProcess(argv, returncode, stdout="partial output\n", stderr="boom\n")
        output = {
            "nmap": """Nmap scan report for localhost
Host is up.
PORT   STATE SERVICE VERSION
80/tcp open  http    nginx 1.24.0
""",
            "httpx": "https://localhost [200] [Welcome] [nginx]\n",
            "crawler": '{"type":"page","url":"https://localhost/","status":200,"title":"Welcome","content_type":"text/html","depth":0,"bytes":120,"truncated":false}\n{"type":"summary","visited":1,"successful":1}\n',
            "nuclei": json.dumps(
                {
                    "template-id": "demo-check",
                    "info": {"name": "Demo Exposure", "severity": "medium"},
                    "matched-at": "https://localhost/demo",
                    "type": "http",
                }
            )
            + "\n",
        }[_tool_name(argv)]
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
        StepExecutionState.SUCCEEDED,
        StepExecutionState.WAITING_APPROVAL,
    ]
    assert [_tool_name(call) for call in calls] == ["nmap", "httpx", "crawler"]
    assert len(run.observations) == 3
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
    assert [_tool_name(call) for call in calls] == ["nmap", "httpx", "crawler", "nuclei"]
    assert len(run.observations) == 4


def test_coordinator_stops_after_execution_failure_and_keeps_raw_evidence(tmp_path):
    runtime, calls = _runtime(tmp_path, returncode=1)
    plan = MissionPlanner(runtime).plan("localhost")

    run = MissionCoordinator(runtime).run(plan)

    assert run.state is MissionRunState.FAILED
    assert run.steps[0].state is StepExecutionState.FAILED
    assert run.steps[0].error == "execution exited with code 1"
    assert run.steps[0].evidence_id == run.evidence[0].id
    assert run.evidence[0].stdout == "partial output\n"
    assert run.evidence[0].stderr == "boom\n"
    assert run.evidence[0].exit_code == 1
    assert run.steps[1].state is StepExecutionState.PENDING
    assert len(calls) == 1
    assert run.finished_at is not None
    assert any(node.kind == "evidence" for node in run.graph.nodes.values())
    assert any(node.kind == "reasoning.stop" for node in run.graph.nodes.values())
