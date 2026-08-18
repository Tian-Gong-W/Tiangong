from __future__ import annotations

import json
import subprocess

import pytest

from tonmen.agents import MissionPlanner
from tonmen.core.config import TonmenConfig
from tonmen.core.runtime import TonmenRuntime
from tonmen.dashboard.server import _STATIC_TYPES, DashboardState
from tonmen.jobs import JobManager
from tonmen.loop import MissionLoop, MissionLoopPolicy
from tonmen.missions import MissionRunState
from tonmen.reports import ReportStore, build_report


def _runtime(tmp_path):
    runtime = TonmenRuntime.sentinel(TonmenConfig(workspace=tmp_path, allowed_targets=("localhost",)))
    nuclei = {
        "template": "http/cves/2014/CVE-2014-2323.yaml",
        "template-id": "CVE-2014-2323",
        "template-path": "/home/test/nuclei-templates/http/cves/2014/CVE-2014-2323.yaml",
        "info": {
            "name": "Lighttpd SQL Injection and Path Traversal",
            "severity": "critical",
            "description": "test description",
            "remediation": "upgrade",
        },
        "host": "localhost",
        "ip": "127.0.0.1",
        "matched-at": "https://localhost/etc/passwd",
        "matcher-status": True,
        "request": "GET /etc/passwd HTTP/1.1\r\nHost: test\r\n\r\n",
        "response": "HTTP/1.1 200 OK\r\n\r\nroot:x:0:0:root:/root:/bin/bash\n",
    }
    outputs = {
        "nmap": "Nmap scan report for localhost\nHost is up.\n80/tcp open http\n443/tcp open https\n",
        "httpx": "https://localhost [200] [Welcome] [nginx]\n",
        "nuclei": json.dumps(nuclei) + "\n",
    }

    def fake_runner(argv, **kwargs):
        return subprocess.CompletedProcess(argv, 0, stdout=outputs.get(argv[0], ""), stderr="")

    runtime.executor._runner = fake_runner
    runtime.jobs = JobManager(runtime.executor)
    return runtime


def _completed_run(tmp_path, *, rounds=8, agents=4):
    runtime = _runtime(tmp_path)
    policy = MissionLoopPolicy(assessment_rounds=rounds, subagents_per_round=agents)
    plan = MissionPlanner(runtime).plan("localhost")
    first = MissionLoop(runtime, policy).run(plan)
    assert first.run.state is MissionRunState.WAITING_APPROVAL
    waiting = plan.steps[-1]
    grant = runtime.approvals.issue(tool=waiting.tool, target=waiting.target)
    second = MissionLoop(runtime, policy).resume(
        plan,
        first.run,
        approval_tokens={waiting.id: grant.token},
    )
    assert second.run.state is MissionRunState.SUCCEEDED
    return runtime, plan, second.run


def test_assessment_policy_is_bounded_to_requested_ranges():
    MissionLoopPolicy(assessment_rounds=7, subagents_per_round=3)
    MissionLoopPolicy(assessment_rounds=10, subagents_per_round=5)
    with pytest.raises(ValueError, match="assessment_rounds"):
        MissionLoopPolicy(assessment_rounds=6)
    with pytest.raises(ValueError, match="assessment_rounds"):
        MissionLoopPolicy(assessment_rounds=11)
    with pytest.raises(ValueError, match="subagents_per_round"):
        MissionLoopPolicy(subagents_per_round=2)
    with pytest.raises(ValueError, match="subagents_per_round"):
        MissionLoopPolicy(subagents_per_round=6)


def test_complex_terminal_mission_expands_within_round_and_agent_bounds(tmp_path):
    _, _, run = _completed_run(tmp_path, rounds=8, agents=4)

    rounds = [node for node in run.graph.nodes.values() if node.kind == "council.round"]
    agents = [node for node in run.graph.nodes.values() if node.kind == "council.subagent"]

    assert len(rounds) == 10
    assert [node.metadata["round"] for node in rounds] == list(range(1, 11))
    assert all(3 <= int(node.metadata["agents"]) <= 5 for node in rounds)
    assert 3 * len(rounds) <= len(agents) <= 5 * len(rounds)
    assert all(node.metadata["execution_authority"] is False for node in agents)
    assert all(node.metadata["recommended_action"] for node in agents)
    assert all(node.metadata["report_only"] is True for node in agents)


def test_complete_report_contains_executed_payload_request_response_and_council(tmp_path):
    _, plan, run = _completed_run(tmp_path)

    report = build_report(plan, run)
    rounds = [node for node in run.graph.nodes.values() if node.kind == "council.round"]
    agents = [node for node in run.graph.nodes.values() if node.kind == "council.subagent"]

    assert report["report_type"] == "final"
    assert report["summary"]["assessment_rounds"] == len(rounds) == 10
    assert report["summary"]["subagent_reviews"] == len(agents)
    assert report["summary"]["executed_payloads"] == 1
    payload = report["executed_payloads"][0]
    assert payload["template_id"] == "CVE-2014-2323"
    assert "GET /etc/passwd" in payload["request"]
    assert "root:x:0:0" in payload["response"]
    assert payload["matcher_status"] is True
    assert report["evidence"][-1]["tool"] == "nuclei"
    assert report["governance"]["approval_tokens_persisted"] is False
    assert report["governance"]["arbitrary_shell"] is False
    assert any(node.kind == "governance.report_gate" for node in run.graph.nodes.values())


def test_report_store_persists_json_and_markdown(tmp_path):
    _, plan, run = _completed_run(tmp_path)
    store = ReportStore(tmp_path)

    stored = store.save(plan, run)
    loaded = store.load_json(run.id)
    markdown = store.load_markdown(run.id)

    assert loaded["mission"]["run_id"] == run.id
    assert loaded["summary"] == stored["summary"]
    assert "# TONMEN Mission Report" in markdown
    assert "## Executed Requests / Payloads" in markdown
    assert "GET /etc/passwd" in markdown
    assert "## Assessment Council" in markdown


def test_dashboard_checkpoint_exposes_report_and_report_ready_event(tmp_path):
    state = DashboardState(TonmenConfig(workspace=tmp_path, allowed_targets=("localhost",)))
    runtime = state.runtime
    outputs = {
        "nmap": "Nmap scan report for localhost\nHost is up.\n80/tcp open http\n",
        "httpx": "https://localhost [200] [Welcome] [nginx]\n",
    }

    def fake_runner(argv, **kwargs):
        return subprocess.CompletedProcess(argv, 0, stdout=outputs.get(argv[0], ""), stderr="")

    runtime.executor._runner = fake_runner
    runtime.jobs = JobManager(runtime.executor)
    plan = MissionPlanner(runtime).plan("localhost")
    result = MissionLoop(runtime, MissionLoopPolicy(), checkpoint=state._checkpoint).run(plan)

    interim = state.report(result.run.id)
    assert interim["mission"]["run_id"] == result.run.id
    assert interim["report_type"] == "interim"
    assert _STATIC_TYPES["reports.js"].startswith("text/javascript")
    assert _STATIC_TYPES["reports.css"].startswith("text/css")


def test_dashboard_terminal_checkpoint_publishes_final_report_event(tmp_path):
    state = DashboardState(TonmenConfig(workspace=tmp_path, allowed_targets=("localhost",)))
    runtime = state.runtime
    plan = MissionPlanner(runtime).plan("localhost")
    outputs = {
        "nmap": "Nmap scan report for localhost\nHost is up.\n",
        "httpx": "unparseable output\n",
    }

    def fake_runner(argv, **kwargs):
        return subprocess.CompletedProcess(argv, 0, stdout=outputs.get(argv[0], ""), stderr="")

    runtime.executor._runner = fake_runner
    runtime.jobs = JobManager(runtime.executor)
    result = MissionLoop(runtime, MissionLoopPolicy(), checkpoint=state._checkpoint).run(plan)
    assert result.run.state is MissionRunState.SUCCEEDED

    report = state.report(result.run.id)
    assert report["report_type"] == "final"
    assert 7 <= report["summary"]["assessment_rounds"] <= 10
    events = state.event_stream(0, timeout=0, limit=500)["events"]
    ready = [event for event in events if event["type"] == "report.ready"]
    assert ready
    assert ready[-1]["data"]["mission_id"] == result.run.id
