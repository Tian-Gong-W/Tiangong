from __future__ import annotations

import json
import subprocess

from tonmen.agents import MissionCoordinator, MissionPlanner
from tonmen.core.config import TonmenConfig
from tonmen.core.runtime import TonmenRuntime
from tonmen.jobs import JobManager
from tonmen.missions import MissionRunState, StepExecutionState
from tonmen.reasoning import MissionReasoner, ReasoningAction


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


def _web_outputs(nuclei_severity: str = "medium"):
    return {
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
                "info": {"name": "Demo Exposure", "severity": nuclei_severity},
                "matched-at": "https://localhost/demo",
                "type": "http",
            }
        )
        + "\n",
    }


def test_reasoner_requests_human_approval_from_evidence_backed_web_surface(tmp_path):
    runtime, calls = _runtime(tmp_path, _web_outputs())
    plan = MissionPlanner(runtime).plan("localhost")
    run = MissionCoordinator(runtime).run(plan)

    decision = MissionReasoner().decide(plan, run)

    assert run.state is MissionRunState.WAITING_APPROVAL
    assert decision.action is ReasoningAction.REQUEST_APPROVAL
    assert decision.requires_human is True
    assert decision.next_step_id == plan.steps[-1].id
    assert decision.basis_fact_ids
    assert [_tool_name(call) for call in calls] == ["nmap", "httpx", "crawler"]
    assert not runtime.approvals._grants


def test_reasoner_can_stop_risk_by_skipping_unjustified_validation(tmp_path):
    runtime, calls = _runtime(
        tmp_path,
        {
            "nmap": "Nmap scan report for localhost\nHost is up.\n",
            "httpx": "unparseable output\n",
            "crawler": '{"type":"summary","visited":1,"successful":0}\n',
        },
    )
    plan = MissionPlanner(runtime).plan("localhost")

    run = MissionCoordinator(runtime).run(plan)

    assert run.state is MissionRunState.SUCCEEDED
    assert run.steps[-1].state is StepExecutionState.SKIPPED
    assert run.steps[2].state is StepExecutionState.SKIPPED
    assert [_tool_name(call) for call in calls] == ["nmap", "httpx"]
    decisions = [node for node in run.graph.nodes.values() if node.kind.startswith("reasoning.")]
    assert any(node.kind == "reasoning.skip" for node in decisions)
    assert any(node.kind == "reasoning.complete" for node in decisions)


def test_high_finding_becomes_review_decision_not_auto_escalation(tmp_path):
    runtime, calls = _runtime(tmp_path, _web_outputs("high"))
    plan = MissionPlanner(runtime).plan("localhost")
    coordinator = MissionCoordinator(runtime)
    run = coordinator.run(plan)
    waiting = plan.steps[-1]
    grant = runtime.approvals.issue(tool=waiting.tool, target=waiting.target)

    coordinator.resume(plan, run, approval_tokens={waiting.id: grant.token})
    decision = MissionReasoner().decide(plan, run)

    assert run.state is MissionRunState.SUCCEEDED
    assert decision.action is ReasoningAction.REVIEW
    assert decision.requires_human is True
    assert decision.basis_fact_ids
    assert [_tool_name(call) for call in calls] == ["nmap", "httpx", "crawler", "nuclei"]
    assert any(node.kind == "reasoning.review" for node in run.graph.nodes.values())


def test_reasoning_nodes_keep_fact_provenance(tmp_path):
    runtime, _ = _runtime(tmp_path, _web_outputs())
    plan = MissionPlanner(runtime).plan("localhost")
    run = MissionCoordinator(runtime).run(plan)

    decision_nodes = [node for node in run.graph.nodes.values() if node.kind == "reasoning.request_approval"]
    assert len(decision_nodes) == 1
    basis = decision_nodes[0].metadata["basis_fact_ids"]
    assert basis
    assert all(fact_id in run.graph.nodes for fact_id in basis)
    support_edges = [edge for edge in run.graph.edges if edge.relation == "supports_decision"]
    assert {edge.source for edge in support_edges} >= set(basis)
