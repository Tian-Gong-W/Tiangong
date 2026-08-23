from __future__ import annotations

import json

from tonmen.ai import LeadAIConfig, LeadAIOrchestrator, MistralAgentProvider


def test_mistral_lead_config_uses_pinned_custom_agent(monkeypatch):
    monkeypatch.setenv("MISTRAL_API_KEY", "mistral-test-secret")
    monkeypatch.setenv("TONMEN_AI_PROVIDER", "mistral")
    monkeypatch.setenv("TONMEN_MISTRAL_AGENT_ID", "ag_test_lead")
    monkeypatch.setenv("TONMEN_MISTRAL_AGENT_VERSION", "1")
    monkeypatch.delenv("TONMEN_AI_KEY_ENV", raising=False)

    config = LeadAIConfig.from_env()
    status = config.public_status()

    assert config.provider == "mistral"
    assert config.api_key_env == "MISTRAL_API_KEY"
    assert config.agent_id == "ag_test_lead"
    assert config.agent_version == 1
    assert config.model == "agent:ag_test_lead@1"
    assert config.enabled is True
    assert status["agent_tools_inherited"] is False
    assert "mistral-test-secret" not in json.dumps(status)


def test_mistral_lead_requires_pinned_agent_version(monkeypatch):
    monkeypatch.setenv("MISTRAL_API_KEY", "mistral-test-secret")
    monkeypatch.setenv("TONMEN_AI_PROVIDER", "mistral")
    monkeypatch.setenv("TONMEN_MISTRAL_AGENT_ID", "ag_test_lead")
    monkeypatch.delenv("TONMEN_MISTRAL_AGENT_VERSION", raising=False)

    try:
        LeadAIConfig.from_env()
    except ValueError as exc:
        assert "TONMEN_MISTRAL_AGENT_VERSION" in str(exc)
    else:
        raise AssertionError("Mistral Lead agent must be version-pinned")


def test_mistral_agent_provider_imports_profile_without_agent_tools(monkeypatch):
    monkeypatch.setenv("MISTRAL_API_KEY", "mistral-provider-secret")
    captured = {}

    def loader(url, headers, timeout):
        captured["profile_url"] = url
        captured["profile_headers"] = dict(headers)
        captured["profile_timeout"] = timeout
        return {
            "id": "ag_test_lead",
            "name": "TONMEN Lead",
            "model": "mistral-medium-latest",
            "instructions": "Prioritize hypothesis quality and evidence convergence.",
            "tools": [{"type": "web_search"}],
            "handoffs": ["ag_other"],
            "completion_args": {"temperature": 0.2, "top_p": 0.9},
        }

    def requester(url, headers, body, timeout):
        captured["url"] = url
        captured["headers"] = dict(headers)
        captured["body"] = json.loads(body)
        captured["timeout"] = timeout
        return {
            "id": "mistral-response-1",
            "model": "mistral-medium-latest",
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": json.dumps(
                            {
                                "focus": "evidence_integrity",
                                "objective": "Reconcile evidence before the next action.",
                                "recommended_action": "continue_governed_plan",
                                "rationale": "The world model still has useful uncertainty.",
                                "confidence": 0.87,
                            }
                        ),
                    }
                }
            ],
            "usage": {"prompt_tokens": 120, "completion_tokens": 40, "total_tokens": 160},
        }

    config = LeadAIConfig(
        provider="mistral",
        model="agent:ag_test_lead@1",
        base_url="https://api.mistral.ai/v1",
        api_key_env="MISTRAL_API_KEY",
        timeout_seconds=31,
        agent_id="ag_test_lead",
        agent_version=1,
    )
    provider = MistralAgentProvider(config, requester=requester, loader=loader)
    result = provider.complete_json(system="TONMEN GOVERNANCE", payload={"mission": {"target": "localhost"}})

    assert captured["profile_url"].endswith("/agents/ag_test_lead/versions/1")
    assert captured["url"].endswith("/chat/completions")
    assert captured["headers"]["Authorization"] == "Bearer mistral-provider-secret"
    assert captured["body"]["model"] == "mistral-medium-latest"
    assert captured["body"]["response_format"] == {"type": "json_object"}
    assert captured["body"]["temperature"] == 0.2
    assert captured["body"]["top_p"] == 0.9
    assert "tools" not in captured["body"]
    assert "handoffs" not in captured["body"]
    assert "Prioritize hypothesis quality" in captured["body"]["messages"][0]["content"]
    assert "TONMEN GOVERNANCE" in captured["body"]["messages"][0]["content"]
    assert result["recommended_action"] == "continue_governed_plan"
    assert provider.last_usage == {"input_tokens": 120, "output_tokens": 40, "total_tokens": 160}


def test_orchestrator_activates_mistral_custom_agent_from_environment(monkeypatch):
    monkeypatch.setenv("MISTRAL_API_KEY", "mistral-test-secret")
    monkeypatch.setenv("TONMEN_AI_PROVIDER", "mistral")
    monkeypatch.setenv("TONMEN_MISTRAL_AGENT_ID", "ag_01a02a0f3b857147bda9118a2481a7a1")
    monkeypatch.setenv("TONMEN_MISTRAL_AGENT_VERSION", "1")

    lead = LeadAIOrchestrator()
    status = lead.public_status()

    assert lead.enabled is True
    assert isinstance(lead.provider, MistralAgentProvider)
    assert status["provider"] == "mistral"
    assert status["agent_id"] == "ag_01a02a0f3b857147bda9118a2481a7a1"
    assert status["agent_version"] == 1
    assert status["active"] is True
