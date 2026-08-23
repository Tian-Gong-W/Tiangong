from __future__ import annotations

import json

from tonmen.ai import LeadAIConfig, LeadAIOrchestrator, MistralAgentProvider, OpenAIResponsesProvider, ProviderHub
from tonmen.missions import MissionPlan, MissionRun


def _lead_result(action: str = "continue_governed_plan", confidence: float = 0.8) -> dict[str, object]:
    return {
        "focus": "evidence_integrity",
        "objective": "Reconcile current evidence.",
        "recommended_action": action,
        "rationale": "Stay inside the governed plan.",
        "confidence": confidence,
    }


def test_openai_lead_rewrites_unsupported_action_before_orchestrator_fallback(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-retry-test")
    request_bodies: list[dict[str, object]] = []
    outputs = [
        json.dumps(_lead_result(action="hack_the_planet")),
        json.dumps(_lead_result(action="continue_governed_plan", confidence=0.91)),
    ]

    def requester(url, headers, body, timeout):
        request_bodies.append(json.loads(body))
        return {
            "id": f"resp-{len(request_bodies)}",
            "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
            "output_text": outputs[len(request_bodies) - 1],
        }

    config = LeadAIConfig(provider="openai", model="test-model")
    provider = OpenAIResponsesProvider(config, requester=requester)
    lead = LeadAIOrchestrator(config, provider=provider)
    plan = MissionPlan.create("app.example.test", [])
    run = MissionRun.create(plan)

    directive = lead.direct(plan, run, round_number=1, phase="live", default_focus="scope_and_plan")

    assert directive.source == "model"
    assert directive.recommended_action == "continue_governed_plan"
    assert directive.confidence == 0.91
    assert len(request_bodies) == 2
    retry_input = request_bodies[1]["input"]
    assert retry_input[-2]["role"] == "assistant"
    assert retry_input[-1]["role"] == "system"
    assert "SYSTEM INTERCEPT" in retry_input[-1]["content"][0]["text"]
    assert provider.last_usage == {"input_tokens": 20, "output_tokens": 10, "total_tokens": 30}


def test_mistral_lead_retries_strict_json_and_preserves_agent_constraints(monkeypatch):
    monkeypatch.setenv("MISTRAL_API_KEY", "mistral-retry-test")
    request_bodies: list[dict[str, object]] = []

    def loader(url, headers, timeout):
        return {
            "id": "ag_test_lead",
            "name": "TONMEN Lead",
            "model": "mistral-medium-latest",
            "instructions": "Review evidence only.",
            "completion_args": {"temperature": 0.2},
        }

    outputs = [
        "```json\n" + json.dumps(_lead_result()) + "\n```",
        json.dumps(_lead_result(confidence=0.84)),
    ]

    def requester(url, headers, body, timeout):
        request_bodies.append(json.loads(body))
        return {
            "id": f"mistral-{len(request_bodies)}",
            "model": "mistral-medium-latest",
            "choices": [{"message": {"role": "assistant", "content": outputs[len(request_bodies) - 1]}}],
            "usage": {"prompt_tokens": 7, "completion_tokens": 3, "total_tokens": 10},
        }

    config = LeadAIConfig(
        provider="mistral",
        model="agent:ag_test_lead@1",
        base_url="https://api.mistral.ai/v1",
        api_key_env="MISTRAL_API_KEY",
        agent_id="ag_test_lead",
        agent_version=1,
    )
    provider = MistralAgentProvider(config, requester=requester, loader=loader)

    def validator(result):
        if result["recommended_action"] != "continue_governed_plan":
            raise ValueError("unsupported action")

    result = provider.complete_json(
        system="TONMEN GOVERNANCE",
        payload={"mission": {"target": "localhost"}},
        validator=validator,
    )

    assert result["confidence"] == 0.84
    assert len(request_bodies) == 2
    retry_messages = request_bodies[1]["messages"]
    assert retry_messages[-2]["role"] == "assistant"
    assert retry_messages[-1]["role"] == "user"
    assert "SYSTEM INTERCEPT" in retry_messages[-1]["content"]
    assert request_bodies[1]["response_format"] == {"type": "json_object"}
    assert "tools" not in request_bodies[1]
    assert provider.last_usage == {"input_tokens": 14, "output_tokens": 6, "total_tokens": 20}


def test_deepseek_pool_retries_invalid_json_then_disallowed_action(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "deepseek-retry-test")
    hub = ProviderHub(pool=("deepseek",))
    request_bodies: list[dict[str, object]] = []

    outputs = [
        "```json\n"
        + json.dumps(
            {
                "summary": "first",
                "recommended_action": "continue_governed_plan",
                "confidence": 0.7,
            }
        )
        + "\n```",
        json.dumps(
            {
                "summary": "second",
                "recommended_action": "hack_the_planet",
                "confidence": 0.7,
            }
        ),
        json.dumps(
            {
                "summary": "corrected",
                "recommended_action": "continue_governed_plan",
                "confidence": 0.79,
            }
        ),
    ]

    def request_json(url, headers, body, timeout=45):
        request_bodies.append(dict(body))
        return {
            "choices": [{"message": {"role": "assistant", "content": outputs[len(request_bodies) - 1]}}],
            "usage": {"prompt_tokens": 9, "completion_tokens": 4, "total_tokens": 13},
        }

    monkeypatch.setattr(hub, "_request_json", request_json)
    result, usage, estimated = hub.complete_json(
        "deepseek",
        None,
        system="Return one bounded review.",
        payload={"facts": []},
    )

    assert result["summary"] == "corrected"
    assert estimated is False
    assert usage == {"input_tokens": 27, "output_tokens": 12, "total_tokens": 39}
    assert len(request_bodies) == 3
    assert request_bodies[1]["messages"][-2]["role"] == "assistant"
    assert "SYSTEM INTERCEPT" in request_bodies[1]["messages"][-1]["content"]
    assert request_bodies[2]["messages"][-2]["role"] == "assistant"
    assert "unsupported recommended_action" in request_bodies[2]["messages"][-1]["content"]


def test_deepseek_pool_exhaustion_counts_retry_tokens_before_failover(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "deepseek-retry-test")
    hub = ProviderHub(pool=("deepseek",))

    def request_json(url, headers, body, timeout=45):
        return {
            "choices": [{"message": {"role": "assistant", "content": "not-json"}}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 2, "total_tokens": 7},
        }

    monkeypatch.setattr(hub, "_request_json", request_json)
    review = hub.review(
        "evidence_verifier",
        system="Return one bounded review.",
        payload={"facts": []},
        fallback_summary="fallback",
        fallback_action="review_failure_evidence",
    )

    assert review.source == "deterministic"
    assert "after 3 attempts" in (review.error or "")
    assert hub.usage["deepseek"].calls == 1
    assert hub.usage["deepseek"].failures == 1
    assert hub.usage["deepseek"].total_tokens == 21
