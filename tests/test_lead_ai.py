from __future__ import annotations

import json
from datetime import datetime, timezone

from tonmen.ai import LeadAIConfig, LeadAIOrchestrator, OpenAIResponsesProvider
from tonmen.council import AssessmentCouncil
from tonmen.evidence import EvidenceRecord, GraphNode
from tonmen.missions import MissionPlan, MissionRun


class FakeLeadProvider:
    def __init__(self, result):
        self.result = result
        self.system = None
        self.payload = None

    def complete_json(self, *, system, payload):
        self.system = system
        self.payload = payload
        return dict(self.result)


def _run_with_secret_evidence():
    plan = MissionPlan.create("app.example.test", [])
    run = MissionRun.create(plan)
    now = datetime.now(timezone.utc)
    run.evidence.append(
        EvidenceRecord(
            id="e-secret",
            tool="httpx",
            target="app.example.test",
            argv=("httpx", "-u", "app.example.test"),
            exit_code=0,
            stdout="SUPER_SECRET_RAW_RESPONSE\nAuthorization: Bearer do-not-send\n",
            stderr="PRIVATE_STDERR\n",
            started_at=now,
            finished_at=now,
        )
    )
    return plan, run


def test_api_key_does_not_auto_enable_provider_or_leak(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-super-secret")
    monkeypatch.delenv("TONMEN_AI_PROVIDER", raising=False)

    disabled = LeadAIConfig.from_env()
    assert disabled.provider == "disabled"
    assert disabled.enabled is False
    assert disabled.key_configured is True

    monkeypatch.setenv("TONMEN_AI_PROVIDER", "openai")
    enabled = LeadAIConfig.from_env()
    status = enabled.public_status()
    assert enabled.enabled is True
    assert status["key_configured"] is True
    assert status["secret_persisted"] is False
    assert "sk-test-super-secret" not in json.dumps(status)
    assert "sk-test-super-secret" not in repr(enabled)


def test_openai_base_url_accepts_official_regional_host_and_rejects_third_party(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-region-test")
    monkeypatch.setenv("TONMEN_AI_PROVIDER", "openai")
    monkeypatch.setenv("TONMEN_OPENAI_BASE_URL", "https://ae.api.openai.com/v1")
    regional = LeadAIConfig.from_env()
    assert regional.base_url == "https://ae.api.openai.com/v1"

    monkeypatch.setenv("TONMEN_OPENAI_BASE_URL", "https://example.invalid/v1")
    try:
        LeadAIConfig.from_env()
    except ValueError as exc:
        assert "official" in str(exc)
    else:
        raise AssertionError("OpenAI key must not be deliverable to a third-party host")

    # Optional AI configuration errors must not stop the governed runtime.
    lead = LeadAIOrchestrator()
    status = lead.public_status()
    assert lead.enabled is False
    assert status["error"] and "official" in str(status["error"])
    plan = MissionPlan.create("app.example.test", [])
    run = MissionRun.create(plan)
    directive = lead.direct(plan, run, round_number=1, phase="live", default_focus="scope_and_plan")
    assert directive.source == "deterministic"
    assert directive.error and "official" in directive.error


def test_openai_responses_provider_uses_server_side_bearer_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-provider-secret")
    captured = {}

    def requester(url, headers, body, timeout):
        captured.update(url=url, headers=dict(headers), body=json.loads(body), timeout=timeout)
        return {
            "output": [
                {
                    "type": "message",
                    "content": [
                        {
                            "type": "output_text",
                            "text": json.dumps(
                                {
                                    "focus": "evidence_integrity",
                                    "objective": "Reconcile evidence provenance.",
                                    "recommended_action": "continue_governed_plan",
                                    "rationale": "Evidence remains bounded.",
                                    "confidence": 0.82,
                                }
                            ),
                        }
                    ],
                }
            ]
        }

    config = LeadAIConfig(provider="openai", model="test-model")
    provider = OpenAIResponsesProvider(config, requester=requester)
    result = provider.complete_json(system="system", payload={"x": 1})

    assert captured["url"].endswith("/responses")
    assert captured["headers"]["Authorization"] == "Bearer sk-provider-secret"
    assert captured["body"]["model"] == "test-model"
    assert result["recommended_action"] == "continue_governed_plan"


def test_lead_ai_receives_metadata_not_raw_evidence():
    plan, run = _run_with_secret_evidence()
    fake = FakeLeadProvider(
        {
            "focus": "evidence_integrity",
            "objective": "Verify provenance without raw payload exposure.",
            "recommended_action": "continue_governed_plan",
            "rationale": "Metadata is sufficient for this review round.",
            "confidence": 0.91,
        }
    )
    lead = LeadAIOrchestrator(LeadAIConfig(provider="openai", model="test-model"), provider=fake)

    directive = lead.direct(plan, run, round_number=1, phase="live", default_focus="scope_and_plan")

    serialized = json.dumps(fake.payload)
    assert directive.source == "model"
    assert directive.model == "test-model"
    assert "SUPER_SECRET_RAW_RESPONSE" not in serialized
    assert "PRIVATE_STDERR" not in serialized
    assert "do-not-send" not in serialized
    assert fake.payload["evidence"][0]["stdout_bytes"] > 0
    assert fake.payload["constraints"]["raw_evidence_included"] is False


def test_unsupported_model_action_falls_back_without_authority():
    plan, run = _run_with_secret_evidence()
    fake = FakeLeadProvider(
        {
            "focus": "attack",
            "objective": "Do something outside the plan.",
            "recommended_action": "run_arbitrary_shell",
            "rationale": "bad",
            "confidence": 1.0,
        }
    )
    lead = LeadAIOrchestrator(LeadAIConfig(provider="openai", model="test-model"), provider=fake)

    directive = lead.direct(plan, run, round_number=1, phase="live", default_focus="scope_and_plan")

    assert directive.source == "deterministic"
    assert directive.recommended_action == "continue_governed_plan"
    assert directive.error and "unsupported" in directive.error
    assert directive.metadata()["execution_authority"] is False
    assert directive.metadata()["approval_authority"] is False
    assert directive.metadata()["scope_authority"] is False


def test_council_has_one_lead_directive_over_three_to_five_subagents():
    plan = MissionPlan.create("app.example.test", [])
    run = MissionRun.create(plan)
    run.graph.add_node(GraphNode(id=run.id, kind="mission", label="mission:app.example.test"))
    fake = FakeLeadProvider(
        {
            "focus": "network_surface",
            "objective": "Reconcile the current surface before the next governed step.",
            "recommended_action": "continue_governed_plan",
            "rationale": "No human boundary is currently required.",
            "confidence": 0.88,
        }
    )
    lead = LeadAIOrchestrator(LeadAIConfig(provider="openai", model="test-model"), provider=fake)
    council = AssessmentCouncil(target_rounds=7, agents_per_round=3, lead_ai=lead)

    round_id = council.record_round(plan, run, session_id="session-1", phase="live")

    assert round_id
    leads = [node for node in run.graph.nodes.values() if node.kind == "council.lead"]
    subagents = [node for node in run.graph.nodes.values() if node.kind == "council.subagent"]
    rounds = [node for node in run.graph.nodes.values() if node.kind == "council.round"]
    assert len(leads) == 1
    assert len(rounds) == 1
    assert len(subagents) == 3
    assert rounds[0].metadata["lead_directive_id"] == leads[0].id
    assert rounds[0].metadata["lead_source"] == "model"
    assert all(node.metadata["lead_directive_id"] == leads[0].id for node in subagents)
    assert all(node.metadata["execution_authority"] is False for node in subagents)
    assert leads[0].metadata["execution_authority"] is False
