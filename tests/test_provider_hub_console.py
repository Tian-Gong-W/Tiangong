from __future__ import annotations

import json
from importlib import resources

from tonmen.ai import ProviderHub
from tonmen.core.config import TonmenConfig
from tonmen.dashboard import DashboardState
from tonmen.evidence import GraphNode
from tonmen.missions import MissionPlan, MissionRun


def test_provider_hub_console_assets_are_packaged():
    static = resources.files("tonmen.dashboard.static")
    html = static.joinpath("provider-hub-page.html").read_text(encoding="utf-8")
    js = static.joinpath("provider-hub-page.js").read_text(encoding="utf-8")
    css = static.joinpath("provider-hub-page.css").read_text(encoding="utf-8")

    assert "AI 配置" in html
    assert "AI PROVIDER CONTROL PLANE" not in html
    assert "登录" in js
    assert "/api/ai/providers/" in js
    assert "data-provider-login" in js
    assert "password" not in html.lower()
    assert "localStorage" not in js
    assert "provider-grid" in css


def test_provider_hub_public_payload_never_exposes_api_key(tmp_path, monkeypatch):
    secret = "deepseek-console-secret-never-public"
    monkeypatch.setenv("TONMEN_AI_POOL", "deepseek,mistral")
    monkeypatch.setenv("DEEPSEEK_API_KEY", secret)
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
    state = DashboardState(TonmenConfig(workspace=tmp_path, config_path=tmp_path / "tonmen.toml"))

    payload = state.provider_hub()
    rendered = json.dumps(payload)

    assert secret not in rendered
    assert payload["pool"] == ["deepseek", "mistral"]
    deepseek = next(item for item in payload["providers"] if item["id"] == "deepseek")
    assert deepseek["key_configured"] is True
    assert deepseek["secret_persisted_by_tonmen"] is False
    assert deepseek["secret_exposed_to_browser"] is False
    assert payload["privacy"]["credential_values_exposed"] is False


def test_provider_hub_aggregates_persisted_subagent_token_usage(tmp_path, monkeypatch):
    monkeypatch.setenv("TONMEN_AI_POOL", "deepseek,mistral")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "x")
    monkeypatch.setenv("MISTRAL_API_KEY", "y")
    state = DashboardState(TonmenConfig(workspace=tmp_path, config_path=tmp_path / "tonmen.toml"))

    plan = MissionPlan.create("example.test", [])
    run = MissionRun.create(plan)
    run.graph.add_node(GraphNode(id=run.id, kind="mission", label="mission"))
    run.graph.add_node(
        GraphNode(
            id="subagent-deepseek",
            kind="council.subagent",
            label="evidence verifier",
            metadata={
                "role": "evidence_verifier",
                "source": "model",
                "provider": "deepseek",
                "model": "deepseek-test",
                "input_tokens": 600,
                "output_tokens": 100,
                "total_tokens": 700,
                "usage_estimated": False,
                "provider_error": None,
            },
        )
    )
    run.graph.add_node(
        GraphNode(
            id="subagent-mistral",
            kind="council.subagent",
            label="remediation editor",
            metadata={
                "role": "remediation_editor",
                "source": "model",
                "provider": "mistral",
                "model": "mistral-test",
                "input_tokens": 200,
                "output_tokens": 100,
                "total_tokens": 300,
                "usage_estimated": True,
                "provider_error": None,
            },
        )
    )
    state.chronicle.save(plan, run)

    payload = state.provider_hub()
    usage = payload["historical_usage"]["providers"]

    assert payload["historical_usage"]["total_calls"] == 2
    assert payload["historical_usage"]["total_tokens"] == 1000
    assert usage["deepseek"]["total_tokens"] == 700
    assert usage["mistral"]["total_tokens"] == 300
    assert usage["mistral"]["estimated_calls"] == 1
    distribution = {item["provider"]: item for item in payload["distribution"]}
    assert distribution["deepseek"]["token_share_percent"] == 70.0
    assert distribution["mistral"]["token_share_percent"] == 30.0


def test_console_browser_login_delegates_to_official_cli(tmp_path, monkeypatch):
    state = DashboardState(TonmenConfig(workspace=tmp_path, config_path=tmp_path / "tonmen.toml"))
    monkeypatch.setattr("tonmen.ai.hub.shutil.which", lambda name: f"/usr/bin/{name}")
    captured = {}

    class Process:
        pid = 8181

    def fake_popen(argv, shell=False):
        captured["argv"] = list(argv)
        captured["shell"] = shell
        return Process()

    monkeypatch.setattr("tonmen.ai.hub.subprocess.Popen", fake_popen)
    result = state.launch_provider_login("chatgpt")

    assert captured == {"argv": ["codex", "login"], "shell": False}
    assert result["provider"] == "chatgpt"
    assert result["pid"] == 8181
    assert "command" not in result
    assert "credentials" in result["note"]


def test_provider_probe_does_not_echo_cli_output_to_browser(tmp_path, monkeypatch):
    state = DashboardState(TonmenConfig(workspace=tmp_path, config_path=tmp_path / "tonmen.toml"))
    monkeypatch.setattr("tonmen.ai.hub.shutil.which", lambda name: f"/usr/bin/{name}")
    sensitive_cli_output = "authenticated token=should-never-be-returned"
    monkeypatch.setattr(ProviderHub, "probe", lambda self, provider_id: {"ready": True, "detail": sensitive_cli_output})

    result = state.probe_provider("grok")

    assert result["ready"] is True
    assert sensitive_cli_output not in json.dumps(result)
    assert result["detail"] == "official CLI reports authenticated / ready"
