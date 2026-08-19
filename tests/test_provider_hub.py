from __future__ import annotations

import json

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
