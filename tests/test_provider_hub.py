from __future__ import annotations

import json
from types import SimpleNamespace

from tonmen.ai import ProviderHub


def test_subagent_pool_requires_explicit_opt_in(monkeypatch):
    monkeypatch.setenv("TONMEN_AI_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "should-not-trigger-subagents")
    monkeypatch.delenv("TONMEN_AI_POOL", raising=False)

    hub = ProviderHub()

    assert hub.pool == ()
    assert hub.select("vulnerability_analyst") is None


def test_public_provider_status_never_contains_secret(monkeypatch):
    secret = "deepseek-secret-value-never-public"
    monkeypatch.setenv("TONMEN_AI_POOL", "deepseek")
    monkeypatch.setenv("DEEPSEEK_API_KEY", secret)
    hub = ProviderHub()

    payload = hub.public_status()
    rendered = json.dumps(payload)

    assert payload["pool"] == ["deepseek"]
    assert secret not in rendered
    provider = next(item for item in payload["providers"] if item["id"] == "deepseek")
    assert provider["key_configured"] is True
    assert provider["secret_persisted_by_tonmen"] is False
    assert provider["secret_exposed_to_browser"] is False


def test_weighted_least_usage_spreads_subagent_calls(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "x")
    monkeypatch.setenv("MISTRAL_API_KEY", "y")
    hub = ProviderHub(pool=("deepseek", "mistral"))

    def fake_complete(provider_id, model, *, system, payload):
        return (
            {
                "summary": f"reviewed by {provider_id}",
                "recommended_action": "continue_governed_plan",
                "confidence": 0.8,
            },
            {"input_tokens": 600, "output_tokens": 100, "total_tokens": 700},
            False,
        )

    monkeypatch.setattr(hub, "complete_json", fake_complete)
    first = hub.review(
        "surface_mapper",
        system="system",
        payload={"facts": []},
        fallback_summary="fallback",
        fallback_action="continue_governed_plan",
    )
    second = hub.review(
        "surface_mapper",
        system="system",
        payload={"facts": []},
        fallback_summary="fallback",
        fallback_action="continue_governed_plan",
    )

    assert first.source == "model"
    assert second.source == "model"
    assert {first.provider, second.provider} == {"deepseek", "mistral"}
    assert sum(item.total_tokens for item in hub.usage.values()) == 1400


def test_role_route_can_pin_provider_and_model(monkeypatch):
    hub = ProviderHub(pool=("grok", "google"))
    monkeypatch.setattr(hub, "is_ready", lambda provider_id: True)
    monkeypatch.setenv("TONMEN_AI_ROUTE_VULNERABILITY_ANALYST", "grok:grok-4.5")

    assert hub.select("vulnerability_analyst") == ("grok", "grok-4.5")


def test_provider_failure_degrades_without_execution_authority(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "x")
    hub = ProviderHub(pool=("deepseek",))

    def fail(*args, **kwargs):
        raise RuntimeError("quota exhausted")

    monkeypatch.setattr(hub, "complete_json", fail)
    review = hub.review(
        "evidence_verifier",
        system="system",
        payload={"raw_evidence_included": False},
        fallback_summary="deterministic evidence summary",
        fallback_action="review_failure_evidence",
    )

    assert review.source == "deterministic"
    assert review.summary == "deterministic evidence summary"
    assert review.recommended_action == "review_failure_evidence"
    assert review.provider == "deepseek"
    assert "quota exhausted" in (review.error or "")
    assert hub.usage["deepseek"].failures == 1


def test_provider_failure_fails_over_to_next_ready_provider(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "x")
    monkeypatch.setenv("MISTRAL_API_KEY", "y")
    hub = ProviderHub(pool=("deepseek", "mistral"))
    calls: list[str] = []

    def fake_complete(provider_id, model, *, system, payload):
        calls.append(provider_id)
        if provider_id == "deepseek":
            raise RuntimeError("429 quota exhausted")
        return (
            {
                "summary": "review recovered on backup provider",
                "recommended_action": "continue_governed_plan",
                "confidence": 0.77,
            },
            {"input_tokens": 400, "output_tokens": 80, "total_tokens": 480},
            False,
        )

    monkeypatch.setattr(hub, "complete_json", fake_complete)
    review = hub.review(
        "surface_mapper",
        system="system",
        payload={"facts": []},
        fallback_summary="fallback",
        fallback_action="continue_governed_plan",
    )

    assert calls == ["deepseek", "mistral"]
    assert review.source == "model"
    assert review.provider == "mistral"
    assert review.total_tokens == 480
    assert "failover recovered" in (review.error or "")
    assert hub.usage["deepseek"].failures == 1
    assert hub.failover_events == 1


def test_provider_token_budget_moves_work_to_remaining_capacity(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "x")
    monkeypatch.setenv("MISTRAL_API_KEY", "y")
    monkeypatch.setenv("TONMEN_AI_PROVIDER_TOKEN_BUDGETS", "deepseek=500,mistral=5000")
    hub = ProviderHub(pool=("deepseek", "mistral"))
    hub.usage["deepseek"].total_tokens = 500

    selected = hub.select("surface_mapper")

    assert selected is not None
    assert selected[0] == "mistral"
    status = hub.public_status()
    deepseek = next(item for item in status["providers"] if item["id"] == "deepseek")
    assert deepseek["tonmen_token_budget"] == 500
    assert deepseek["tonmen_tokens_remaining"] == 0


def test_mission_token_budget_stops_more_model_calls(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "x")
    monkeypatch.setenv("TONMEN_AI_MISSION_TOKEN_BUDGET", "1000")
    hub = ProviderHub(pool=("deepseek",))
    hub.usage["deepseek"].total_tokens = 1000

    def should_not_call(*args, **kwargs):
        raise AssertionError("provider should not be called after mission budget exhaustion")

    monkeypatch.setattr(hub, "complete_json", should_not_call)
    review = hub.review(
        "evidence_verifier",
        system="system",
        payload={},
        fallback_summary="budget fallback",
        fallback_action="finalize_report",
    )

    assert review.source == "deterministic"
    assert "mission AI token budget exhausted" in (review.error or "")
    status = hub.public_status()
    assert status["mission_token_budget"] == 1000
    assert status["mission_tokens_remaining"] == 0


def test_persisted_mission_usage_primes_budget_without_double_count(monkeypatch):
    monkeypatch.setenv("TONMEN_AI_MISSION_TOKEN_BUDGET", "2000")
    hub = ProviderHub(pool=())
    node = SimpleNamespace(
        kind="council.subagent",
        metadata={
            "source": "model",
            "provider": "deepseek",
            "input_tokens": 600,
            "output_tokens": 100,
            "total_tokens": 700,
            "usage_estimated": False,
            "provider_error": None,
        },
    )
    run = SimpleNamespace(id="run-1", graph=SimpleNamespace(nodes={"a": node}))

    hub.prime_usage_from_run(run)
    hub.prime_usage_from_run(run)

    assert hub.usage["deepseek"].calls == 1
    assert hub.usage["deepseek"].total_tokens == 700
    assert hub.public_status()["mission_tokens_remaining"] == 1300


def test_browser_login_delegates_to_official_cli_without_reading_credentials(monkeypatch):
    hub = ProviderHub(pool=("grok",))
    monkeypatch.setattr("tonmen.ai.hub.shutil.which", lambda name: f"/usr/bin/{name}")
    captured = {}

    class Process:
        pid = 4242

    def fake_popen(argv, shell=False):
        captured["argv"] = list(argv)
        captured["shell"] = shell
        return Process()

    monkeypatch.setattr("tonmen.ai.hub.subprocess.Popen", fake_popen)
    result = hub.launch_login("grok")

    assert captured == {"argv": ["grok", "login"], "shell": False}
    assert result["pid"] == 4242
    assert "credentials" in result["note"]
