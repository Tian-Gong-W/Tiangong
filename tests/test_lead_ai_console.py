from __future__ import annotations

import json
from importlib import resources

from tonmen.ai import LeadAIConfig, OpenAIResponsesProvider
from tonmen.core.config import TonmenConfig
from tonmen.dashboard import DashboardState
from tonmen.evidence import GraphNode
from tonmen.missions import MissionPlan, MissionRun, MissionRunState
from tonmen.reports import build_report, render_markdown


def _run_with_lead_graph():
    plan = MissionPlan.create("app.example.test", [])
    run = MissionRun.create(plan)
    run.state = MissionRunState.RUNNING

    run.graph.add_node(GraphNode(id=run.id, kind="mission", label="mission:app.example.test"))
    run.graph.add_node(
        GraphNode(
            id="session-1",
            kind="loop.session",
            label="bounded loop",
            metadata={"assessment_rounds": 8, "subagents_per_round": 4},
        )
    )
    run.graph.add_node(
        GraphNode(
            id="lead-1",
            kind="council.lead",
            label="lead directive round 1",
            metadata={
                "round": 1,
                "phase": "live",
                "focus": "network_surface",
                "objective": "Reconcile the observed surface before the next governed step.",
                "recommended_action": "continue_governed_plan",
                "rationale": "Evidence supports continuing the existing bounded plan.",
                "confidence": 0.88,
                "source": "model",
                "provider": "openai",
                "model": "test-model",
                "error": None,
                "latency_ms": 123,
                "input_tokens": 10,
                "output_tokens": 4,
                "total_tokens": 14,
                "execution_authority": False,
                "approval_authority": False,
                "scope_authority": False,
                "raw_evidence_sent": False,
            },
        )
    )
    run.graph.add_node(
        GraphNode(
            id="round-1",
            kind="council.round",
            label="assessment round 1: network_surface",
            metadata={
                "round": 1,
                "focus": "network_surface",
                "phase": "live",
                "agents": 4,
                "session_id": "session-1",
                "lead_directive_id": "lead-1",
                "lead_source": "model",
                "lead_provider": "openai",
                "lead_model": "test-model",
                "lead_recommended_action": "continue_governed_plan",
            },
        )
    )
    run.graph.add_node(
        GraphNode(
            id="agent-1",
            kind="council.subagent",
            label="evidence verifier",
            metadata={
                "role": "evidence_verifier",
                "round": 1,
                "focus": "network_surface",
                "phase": "live",
                "summary": "Verify the evidence chain.",
                "recommended_action": "continue_governed_plan",
                "lead_directive_id": "lead-1",
                "execution_authority": False,
            },
        )
    )
    run.graph.link(run.id, "orchestrated_by", "lead-1")
    run.graph.link("lead-1", "directs", "round-1")
    run.graph.link("round-1", "contains_subagent", "agent-1")
    return plan, run


def test_lead_ai_console_assets_and_native_route_are_packaged():
    static = resources.files("tonmen.dashboard.static")
    html = static.joinpath("index.html").read_text(encoding="utf-8")
    js = static.joinpath("module-pages.js").read_text(encoding="utf-8")
    css = static.joinpath("lead-ai.css").read_text(encoding="utf-8")

    assert 'href="/lead"' in html
    assert '"/lead": ["主导", "主导智能"' in js
    assert 'api("/api/ai/lead")' in js
    assert "提供方：" in js
    assert "密钥已配置：" in js
    assert ".lead-console-grid" in css
    assert ".lead-progress" in css


def test_dashboard_lead_ai_status_never_exposes_api_key(monkeypatch, tmp_path):
    monkeypatch.setenv("TONMEN_AI_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-never-show-this-secret")
    state = DashboardState(TonmenConfig(workspace=tmp_path, config_path=tmp_path / "tonmen.toml"))

    payload = state.lead_ai()
    serialized = json.dumps(payload)

    assert payload["config"]["key_configured"] is True
    assert payload["privacy"]["secret_persisted"] is False
    assert payload["privacy"]["secret_exposed_to_browser"] is False
    assert payload["privacy"]["raw_evidence_sent"] is False
    assert "sk-never-show-this-secret" not in serialized


def test_dashboard_lead_ai_reads_latest_directive_and_telemetry(tmp_path):
    state = DashboardState(TonmenConfig(workspace=tmp_path, config_path=tmp_path / "tonmen.toml"))
    plan, run = _run_with_lead_graph()
    state.chronicle.save(plan, run)

    payload = state.lead_ai()

    assert payload["current"]["mission"]["id"] == run.id
    assert payload["current"]["latest_directive"]["id"] == "lead-1"
    assert payload["current"]["rounds_completed"] == 1
    assert payload["current"]["target_rounds"] == 8
    assert payload["current"]["subagents"][0]["metadata"]["role"] == "evidence_verifier"
    telemetry = payload["current"]["telemetry"]
    assert telemetry["directives"] == 1
    assert telemetry["model_calls"] == 1
    assert telemetry["fallback_calls"] == 0
    assert telemetry["input_tokens"] == 10
    assert telemetry["output_tokens"] == 4
    assert telemetry["total_tokens"] == 14
    assert telemetry["last_latency_ms"] == 123


def test_report_includes_lead_usage_and_round_directive():
    plan, run = _run_with_lead_graph()

    report = build_report(plan, run)

    assert report["lead_ai"]["directive_count"] == 1
    assert report["lead_ai"]["model_calls"] == 1
    assert report["lead_ai"]["fallback_calls"] == 0
    assert report["lead_ai"]["total_tokens"] == 14
    assert report["lead_ai"]["latency_ms_average"] == 123
    assert report["assessment_council"][0]["lead"]["id"] == "lead-1"
    assert report["summary"]["lead_model_calls"] == 1

    markdown = render_markdown(report)
    assert "## Lead AI Orchestration" in markdown
    assert "Lead AI total tokens: 14" in markdown
    assert "### Lead Round 1 — network_surface" in markdown


def test_openai_provider_captures_usage_without_persisting_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-usage-secret")

    def requester(url, headers, body, timeout):
        return {
            "id": "resp-test",
            "usage": {"input_tokens": 12, "output_tokens": 5, "total_tokens": 17},
            "output_text": json.dumps(
                {
                    "focus": "evidence_integrity",
                    "objective": "Review provenance.",
                    "recommended_action": "continue_governed_plan",
                    "rationale": "Evidence is bounded.",
                    "confidence": 0.8,
                }
            ),
        }

    provider = OpenAIResponsesProvider(
        LeadAIConfig(provider="openai", model="test-model"),
        requester=requester,
    )
    provider.complete_json(system="system", payload={"safe": True})

    assert provider.last_usage == {"input_tokens": 12, "output_tokens": 5, "total_tokens": 17}
    assert provider.last_response_id == "resp-test"
    assert "sk-usage-secret" not in repr(provider.last_usage)
