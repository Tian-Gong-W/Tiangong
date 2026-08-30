from __future__ import annotations

import json

from tonmen.ai.config import LeadAIConfig
from tonmen.ai.runtime_provider import ProviderHub
from tonmen.ai.settings import public_settings, update_settings


def _reset_provider_cache() -> None:
    ProviderHub.invalidate_probe()


def test_lead_provider_is_explicitly_persisted(tmp_path, monkeypatch):
    settings_file = tmp_path / "ai-settings.json"
    monkeypatch.setenv("TONMEN_AI_SETTINGS_FILE", str(settings_file))

    saved = update_settings(
        lead_provider="deepseek",
        lead_model="deepseek-v4-flash",
        pool=["deepseek", "chatgpt"],
    )

    assert saved["lead_provider"] == "deepseek"
    assert saved["lead_model"] == "deepseek-v4-flash"
    assert saved["pool"] == ["deepseek", "chatgpt"]
    raw = json.loads(settings_file.read_text(encoding="utf-8"))
    assert raw["lead_provider"] == "deepseek"
    assert public_settings()["lead_provider"] == "deepseek"


def test_legacy_lead_enabled_remains_backward_compatible(tmp_path, monkeypatch):
    monkeypatch.setenv("TONMEN_AI_SETTINGS_FILE", str(tmp_path / "ai-settings.json"))

    enabled = update_settings(lead_enabled=True)
    disabled = update_settings(lead_enabled=False)

    assert enabled["lead_provider"] == "openai"
    assert disabled["lead_provider"] == "disabled"


def test_deepseek_is_a_valid_lead_provider(tmp_path, monkeypatch):
    monkeypatch.setenv("TONMEN_AI_SETTINGS_FILE", str(tmp_path / "ai-settings.json"))
    monkeypatch.setenv("TONMEN_AI_PROVIDER", "deepseek")
    monkeypatch.setenv("TONMEN_AI_MODEL", "deepseek-reasoner")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-only")

    config = LeadAIConfig.from_env()

    assert config.provider == "deepseek"
    assert config.model == "deepseek-reasoner"
    assert config.base_url == "https://api.deepseek.com/v1"
    assert config.api_key_env == "DEEPSEEK_API_KEY"
    assert config.enabled is True


def test_browser_cli_installation_does_not_imply_ready(monkeypatch):
    _reset_provider_cache()
    monkeypatch.setattr(
        "tonmen.ai.hub.ProviderHub.probe",
        lambda self, provider_id, timeout=8: {"ready": False, "detail": "not logged in"},
    )
    hub = ProviderHub(pool=("chatgpt",))

    status = hub.authentication_status("chatgpt")

    assert status["authenticated"] is False
    assert status["runtime_ready"] is False
    assert hub.is_ready("chatgpt") is False


def test_authenticated_antigravity_is_not_routable_by_default(monkeypatch):
    _reset_provider_cache()
    monkeypatch.delenv("TONMEN_ANTIGRAVITY_HEADLESS_ALLOWED", raising=False)
    monkeypatch.setattr(
        "tonmen.ai.hub.ProviderHub.probe",
        lambda self, provider_id, timeout=8: {"ready": True, "detail": "authenticated"},
    )
    hub = ProviderHub(pool=("google",))

    status = hub.authentication_status("google")

    assert status["authenticated"] is True
    assert status["runtime_ready"] is False
    assert "headless Council routing is disabled" in str(status["runtime_blocker"])
    assert hub.select("surface_mapper") is None


def test_antigravity_can_be_explicitly_admitted_after_operator_validation(monkeypatch):
    _reset_provider_cache()
    monkeypatch.setenv("TONMEN_ANTIGRAVITY_HEADLESS_ALLOWED", "1")
    monkeypatch.setattr(
        "tonmen.ai.hub.ProviderHub.probe",
        lambda self, provider_id, timeout=8: {"ready": True, "detail": "authenticated"},
    )
    hub = ProviderHub(pool=("google",))

    status = hub.authentication_status("google")

    assert status["authenticated"] is True
    assert status["runtime_ready"] is True
    selected = hub.select("surface_mapper")
    assert selected is not None
    assert selected[0] == "google"


def test_runtime_probe_never_exposes_credentials(monkeypatch):
    _reset_provider_cache()
    monkeypatch.setattr(
        "tonmen.ai.hub.ProviderHub.probe",
        lambda self, provider_id, timeout=8: {"ready": False, "detail": "login required"},
    )
    status = ProviderHub(pool=("grok",)).authentication_status("grok")

    rendered = json.dumps(status)
    assert "credential" not in rendered.lower()
    assert status["runtime_ready"] is False
