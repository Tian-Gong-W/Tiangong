from __future__ import annotations

import json
import subprocess
from importlib import resources

from tonmen.core.config import TonmenConfig
from tonmen.core.runtime import TonmenRuntime
from tonmen.dashboard import DashboardState
from tonmen.dashboard.mission_workspace import build_mission_workspace
from tonmen.dashboard.mission_workspace_server import MissionWorkspaceDashboardHandler
from tonmen.jobs import JobManager
from tonmen.loop import MissionLoop, MissionLoopPolicy
from tonmen.missions import MissionPlan, MissionRunState, MissionStep


def _plan() -> MissionPlan:
    return MissionPlan.create(
        "localhost",
        [
            MissionStep.create(
                tool="nmap",
                target="localhost",
                parameters={"ports": "80,443", "service_detection": False},
                risk=1,
                requires_approval=False,
                rationale="确认常见 Web 端口。",
            ),
            MissionStep.create(
                tool="httpx",
                target="https://localhost",
                parameters={"follow_redirects": False, "timeout": 10},
                risk=1,
                requires_approval=False,
                rationale="识别网站状态和技术。",
            ),
            MissionStep.create(
                tool="nuclei",
                target="https://localhost",
                parameters={"severity": ("medium", "high", "critical"), "rate_limit": 10, "timeout": 10},
                risk=3,
                requires_approval=True,
                rationale="人工确认后验证漏洞。",
            ),
        ],
        metadata={
            "resolved_assets": {
                "target": "localhost",
                "host": "localhost",
                "assets": [
                    {"address": "127.0.0.1", "family": "ipv4", "authorized": True, "scope_status": "authorized", "source": "dns"},
                    {"address": "203.0.113.10", "family": "ipv4", "authorized": False, "scope_status": "needs_scope", "source": "dns"},
                ],
                "authorized_addresses": ["127.0.0.1"],
                "needs_scope": ["203.0.113.10"],
            },
            "coverage_plan": {
                "direct_nmap_targets": [],
                "resolved_ip_coverage_enabled": False,
            },
        },
    )


def _completed_run(tmp_path):
    runtime = TonmenRuntime.sentinel(TonmenConfig(workspace=tmp_path, allowed_targets=("localhost",)))
    nuclei = {
        "template-id": "demo-confirmed",
        "info": {"name": "Demo Exposure", "severity": "high"},
        "host": "https://localhost",
        "ip": "127.0.0.1",
        "matched-at": "https://localhost/demo",
        "matcher-status": True,
        "type": "http",
        "request": "GET /demo HTTP/1.1\r\nHost: localhost\r\n\r\n",
        "response": "HTTP/1.1 200 OK\r\n\r\nconfirmed-marker\n",
    }
    outputs = {
        "nmap": "Nmap scan report for localhost (127.0.0.1)\nHost is up.\n80/tcp open http\n",
        "httpx": "https://localhost [200] [Welcome] [nginx]\n",
        "nuclei": json.dumps(nuclei) + "\n",
    }

    def fake_runner(argv, **kwargs):
        return subprocess.CompletedProcess(argv, 0, stdout=outputs.get(argv[0], ""), stderr="")

    runtime.executor._runner = fake_runner
    runtime.jobs = JobManager(runtime.executor)
    plan = _plan()
    first = MissionLoop(runtime, MissionLoopPolicy()).run(plan)
    assert first.run.state is MissionRunState.WAITING_APPROVAL
    waiting = plan.steps[-1]
    grant = runtime.approvals.issue(tool=waiting.tool, target=waiting.target)
    second = MissionLoop(runtime, MissionLoopPolicy()).resume(
        plan,
        first.run,
        approval_tokens={waiting.id: grant.token},
    )
    assert second.run.state is MissionRunState.SUCCEEDED
    return plan, second.run


def test_workspace_projects_goals_intents_facts_decisions_and_findings(tmp_path):
    plan, run = _completed_run(tmp_path)
    workspace = build_mission_workspace(plan, run)

    kinds = {node["kind"] for node in workspace["exploration"]["nodes"]}
    relations = {edge["relation"] for edge in workspace["exploration"]["edges"]}

    assert {"goal", "intent", "fact", "decision", "finding"}.issubset(kinds)
    assert {"计划", "发现", "确认"}.issubset(relations)
    assert workspace["exploration"]["counts"]["intents"] == 3
    assert workspace["exploration"]["counts"]["findings"] == 1
    assert workspace["authority"] == {
        "execution": False,
        "approval": False,
        "scope": False,
        "plan_mutation": False,
        "fact_creation": False,
    }


def test_workspace_asset_graph_binds_finding_to_evidenced_backend_without_expanding_scope(tmp_path):
    plan, run = _completed_run(tmp_path)
    workspace = build_mission_workspace(plan, run)
    graph = workspace["assets"]
    nodes = {node["id"]: node for node in graph["nodes"]}

    assert nodes["asset:host:localhost"]["kind"] == "host"
    assert nodes["asset:ip:127.0.0.1"]["coverage_status"] == "scanned"
    assert nodes["asset:ip:203.0.113.10"]["scope_status"] == "needs_scope"
    assert graph["semantics"]["dns_resolution_expands_scope"] is False
    assert graph["semantics"]["finding_affects_only_linked_assets"] is True

    finding = workspace["findings"][0]
    assert finding["affected_asset_ids"] == ["asset:ip:127.0.0.1"]
    assert any(
        edge["source"] == "asset:ip:127.0.0.1" and edge["relation"] == "影响"
        for edge in graph["edges"]
    )


def test_dashboard_mission_payload_adds_workspace_projection(tmp_path):
    plan, run = _completed_run(tmp_path)
    state = DashboardState(TonmenConfig(workspace=tmp_path, allowed_targets=("localhost",)))
    state.chronicle.save(plan, run)

    payload = state.mission(run.id)

    assert payload["id"] == run.id
    assert payload["workspace"]["views"] == ["exploration", "findings", "assets", "report"]
    assert payload["workspace"]["findings"]


def test_mission_workspace_assets_are_packaged():
    static = resources.files("tonmen.dashboard.static")
    js = static.joinpath("mission-workspace.js").read_text(encoding="utf-8")
    css = static.joinpath("mission-workspace.css").read_text(encoding="utf-8")

    for text in ("探索链", "漏洞", "资产", "报告", "为什么继续", "DNS 解析只记录资产"):
        assert text in js
    assert ".mission-workspace-tabs" in css
    assert ".mission-asset-tree" in css
    assert issubclass(MissionWorkspaceDashboardHandler, object)
