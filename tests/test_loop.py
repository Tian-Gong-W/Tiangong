from __future__ import annotations

import json
import subprocess

from tonmen.agents import MissionPlanner
from tonmen.chronicle import ChronicleStore
from tonmen.core.config import TonmenConfig
from tonmen.core.runtime import TonmenRuntime
from tonmen.jobs import JobManager
from tonmen.loop import LoopStopReason, MissionLoop, MissionLoopPolicy
from tonmen.missions import MissionRunState, StepExecutionState


def _outputs(*, web: bool = True, severity: str = "medium"):
    return {
        "nmap": (
            "Nmap scan report for localhost\n"
            "Host is up.\n"
            "PORT   STATE SERVICE VERSION\n"
            + ("80/tcp open  http    nginx 1.24.0\n" if web else "")
        ),
        "httpx": "https://localhost [200] [Welcome] [nginx]\n" if web else "unparseable output\n",
        "crawler": (
            '{"type":"page","url":"https://localhost/","status":200,"title":"Welcome","content_type":"text/html","depth":0,"bytes":100,"truncated":false}\n'
            '{"type":"summary","visited":1,"successful":1}\n'
            if web else '{"type":"summary","visited":1,"successful":0}\n'
        ),
        "nuclei": json.dumps(
            {
                "template-id": "demo-check",
                "info": {"name": "Demo Exposure", "severity": severity},
                "matched-at": "https://localhost/demo",
                "type": "http",
            }
        )
        + "\n",
    }


def _tool_name(argv) -> str:
    if argv and argv[0] in {"nmap", "httpx", "nuclei"}:
        return argv[0]
    if len(argv) >= 3 and argv[1:3] == ["-m", "tonmen.tools.runners.crawler"]:
        return "crawler"
    return str(argv[0]) if argv else "unknown"


def _runtime(tmp_path, outputs):
    runtime = TonmenRuntime.sentinel(TonmenConfig(workspace=tmp_path, allowed_targets=("localhost",)))
    calls: list[list[str]] = []

    def fake_runner(argv, **kwargs):
        calls.append(list(argv))
        return subprocess.CompletedProcess(argv, 0, stdout=outputs.get(_tool_name(argv), ""), stderr="")

    runtime.executor._runner = fake_runner
    runtime.jobs = JobManager(runtime.executor)
    return runtime, calls


def test_loop_stops_at_human_approval_after_discovery(tmp_path):
    runtime, calls = _runtime(tmp_path, _outputs(web=True))
    plan = MissionPlanner(runtime).plan("localhost")

    result = MissionLoop(runtime).run(plan)

    assert result.stop_reason is LoopStopReason.APPROVAL_REQUIRED
    assert result.run.state is MissionRunState.WAITING_APPROVAL
    assert result.executions == 3
    assert [_tool_name(call) for call in calls] == ["nmap", "httpx", "crawler"]
    assert result.run.steps[-1].state is StepExecutionState.WAITING_APPROVAL
    assert any(node.kind == "loop.stop" for node in result.run.graph.nodes.values())
    assert not runtime.approvals._grants


def test_loop_skips_unjustified_web_branches_and_completes(tmp_path):
    runtime, calls = _runtime(tmp_path, _outputs(web=False))
    plan = MissionPlanner(runtime).plan("localhost")

    result = MissionLoop(runtime).run(plan)

    assert result.stop_reason is LoopStopReason.COMPLETE
    assert result.run.state is MissionRunState.SUCCEEDED
    assert result.run.steps[2].state is StepExecutionState.SKIPPED
    assert result.run.steps[-1].state is StepExecutionState.SKIPPED
    assert [_tool_name(call) for call in calls] == ["nmap", "httpx"]
    assert any(node.kind == "reasoning.skip" for node in result.run.graph.nodes.values())


def test_loop_execution_budget_is_a_hard_stop(tmp_path):
    runtime, calls = _runtime(tmp_path, _outputs(web=True))
    plan = MissionPlanner(runtime).plan("localhost")
    policy = MissionLoopPolicy(max_executions=1)

    result = MissionLoop(runtime, policy).run(plan)

    assert result.stop_reason is LoopStopReason.EXECUTION_BUDGET
    assert result.executions == 1
    assert result.run.state is MissionRunState.RUNNING
    assert [_tool_name(call) for call in calls] == ["nmap"]
    assert result.run.steps[0].state is StepExecutionState.SUCCEEDED
    assert result.run.steps[1].state is StepExecutionState.PENDING


def test_approved_loop_resume_executes_only_waiting_step_and_stops_for_review(tmp_path):
    runtime1, calls1 = _runtime(tmp_path, _outputs(web=True, severity="high"))
    plan = MissionPlanner(runtime1).plan("localhost")
    first = MissionLoop(runtime1).run(plan)
    assert first.stop_reason is LoopStopReason.APPROVAL_REQUIRED

    store = ChronicleStore(tmp_path)
    store.save(plan, first.run)
    loaded_plan, loaded_run = store.load(first.run.id)

    runtime2, calls2 = _runtime(tmp_path, _outputs(web=True, severity="high"))
    waiting = loaded_plan.steps[-1]
    grant = runtime2.approvals.issue(tool=waiting.tool, target=waiting.target)

    second = MissionLoop(runtime2).resume(
        loaded_plan,
        loaded_run,
        approval_tokens={waiting.id: grant.token},
    )

    assert [_tool_name(call) for call in calls1] == ["nmap", "httpx", "crawler"]
    assert [_tool_name(call) for call in calls2] == ["nuclei"]
    assert second.stop_reason is LoopStopReason.REVIEW_REQUIRED
    assert second.run.state is MissionRunState.SUCCEEDED
    assert all(step.state is StepExecutionState.SUCCEEDED for step in second.run.steps)


def test_loop_governance_nodes_survive_chronicle(tmp_path):
    runtime, _ = _runtime(tmp_path, _outputs(web=True))
    plan = MissionPlanner(runtime).plan("localhost")
    result = MissionLoop(runtime).run(plan)
    store = ChronicleStore(tmp_path)

    store.save(plan, result.run)
    _, loaded = store.load(result.run.id)

    kinds = [node.kind for node in loaded.graph.nodes.values()]
    assert "loop.session" in kinds
    assert "loop.iteration" in kinds
    assert "loop.stop" in kinds


def test_loop_policy_rejects_unbounded_values():
    try:
        MissionLoopPolicy(max_iterations=0)
    except ValueError as exc:
        assert "max_iterations" in str(exc)
    else:
        raise AssertionError("zero-iteration loop must be rejected")

    try:
        MissionLoopPolicy(max_executions=1000)
    except ValueError as exc:
        assert "max_executions" in str(exc)
    else:
        raise AssertionError("unbounded execution budget must be rejected")

    try:
        MissionLoopPolicy(report_only=False)
    except ValueError as exc:
        assert "report_only" in str(exc)
    else:
        raise AssertionError("report-only boundary must not be disableable")
