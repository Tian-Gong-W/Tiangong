from __future__ import annotations

import json
from importlib import resources

from tonmen.core.config import TonmenConfig
from tonmen.core.runtime import TonmenRuntime
from tonmen.dashboard import DashboardState
from tonmen.dashboard.preflight_server import _mission_policy
from tonmen.preflight import build_mission_preflight
from tonmen.tools import ToolReadiness


_SECRET = "preflight-worker-secret-0123456789-ABCDEFG"


def _ready():
    return ToolReadiness(True, "ready", "test ready")


def _missing(name: str):
    return ToolReadiness(False, "missing_binary", f"{name} missing", remediation=f"install {name}")


def test_console_mission_policy_uses_current_loop_defaults():
    policy = _mission_policy({})
    assert policy.max_iterations == 8
    assert policy.max_executions == 3
    assert policy.max_duration_seconds == 1200
    assert policy.assessment_rounds == 8
    assert policy.subagents_per_round == 4


def test_preflight_reports_timeout_assets_and_empty_ai_pool(monkeypatch, tmp_path):
    monkeypatch.delenv("TONMEN_AI_POOL", raising=False)
    monkeypatch.delenv("TONMEN_AI_PROVIDER", raising=False)
    monkeypatch.delenv("TONMEN_EXECUTION_MODE", raising=False)
    runtime = TonmenRuntime.sentinel(TonmenConfig(workspace=tmp_path, allowed_targets=("localhost",)))
    for adapter in runtime.registry:
        monkeypatch.setattr(adapter, "readiness", _ready)

    payload = build_mission_preflight(runtime, "localhost")

    assert payload["ready_to_start"] is True
    assert payload["policy"]["max_duration_seconds"] == 1200
    assert payload["policy"]["longest_step_timeout_seconds"] == 900
    assert payload["execution_plane"]["mode"] == "local"
    assert payload["side_effects"]["scanner_executed"] is False
    assert payload["side_effects"]["provider_model_called"] is False
    assert any(item["code"] == "ai_provider_pool_empty" for item in payload["warnings"])
    assert all(step["timeout_seconds"] == runtime.config.timeout_for(step["tool"]) for step in payload["steps"])


def test_preflight_blocks_missing_autonomous_tool_but_only_warns_for_future_approval_tool(monkeypatch, tmp_path):
    monkeypatch.delenv("TONMEN_EXECUTION_MODE", raising=False)
    runtime = TonmenRuntime.sentinel(TonmenConfig(workspace=tmp_path, allowed_targets=("localhost",)))
    monkeypatch.setattr(runtime.registry.get("nmap"), "readiness", lambda: _missing("nmap"))
    monkeypatch.setattr(runtime.registry.get("httpx"), "readiness", _ready)
    monkeypatch.setattr(runtime.registry.get("nuclei"), "readiness", lambda: _missing("nuclei"))

    payload = build_mission_preflight(runtime, "localhost")

    assert payload["ready_to_start"] is False
    blockers = [item for item in payload["blockers"] if item["code"] == "tool_not_ready"]
    warnings = [item for item in payload["warnings"] if item["code"] == "tool_not_ready"]
    assert any(item["metadata"]["tool"] == "nmap" for item in blockers)
    assert any(item["metadata"]["tool"] == "nuclei" for item in warnings)


def test_worker_mode_does_not_require_control_plane_scanner_binaries(monkeypatch, tmp_path):
    monkeypatch.setenv("TONMEN_EXECUTION_MODE", "worker")
    monkeypatch.setenv(
        "TONMEN_WORKERS",
        "uae-1@http://127.0.0.1:8890#region=uae#tags=web,nmap,nuclei#secret_env=TONMEN_WORKER_SECRET_UAE1",
    )
    monkeypatch.setenv("TONMEN_WORKER_SECRET_UAE1", _SECRET)
    runtime = TonmenRuntime.sentinel(TonmenConfig(workspace=tmp_path, allowed_targets=("localhost",)))
    for adapter in runtime.registry:
        monkeypatch.setattr(adapter, "readiness", lambda name=adapter.spec.name: _missing(name))

    payload = build_mission_preflight(runtime, "localhost")

    assert payload["ready_to_start"] is True
    assert payload["execution_plane"]["mode"] == "worker"
    assert payload["execution_plane"]["local_scanner_binaries_required"] is False
    assert payload["execution_plane"]["worker_count"] == 1
    assert all(step["readiness"]["code"] == "deferred_to_worker" for step in payload["steps"])
    state = DashboardState(TonmenConfig(workspace=tmp_path, allowed_targets=("localhost",)))
    # Dashboard's start gate must also defer readiness to the remote Worker plane.
    state._require_tool_ready("nmap")


def test_preflight_never_serializes_provider_or_worker_secret(monkeypatch, tmp_path):
    provider_secret = "SUPER-SECRET-PREFLIGHT-OPENAI"
    monkeypatch.setenv("TONMEN_AI_PROVIDER", "openai")
    monkeypatch.setenv("TONMEN_AI_POOL", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", provider_secret)
    monkeypatch.delenv("TONMEN_EXECUTION_MODE", raising=False)
    runtime = TonmenRuntime.sentinel(TonmenConfig(workspace=tmp_path, allowed_targets=("localhost",)))
    for adapter in runtime.registry:
        monkeypatch.setattr(adapter, "readiness", _ready)

    payload = build_mission_preflight(runtime, "localhost")
    rendered = json.dumps(payload)

    assert provider_secret not in rendered
    assert payload["ai"]["secret_values_exposed"] is False
    assert payload["ai"]["approval_tokens_sent"] is False


def test_preflight_assets_are_packaged_and_injected_into_console(tmp_path):
    static = resources.files("tonmen.dashboard.static")
    js = static.joinpath("mission-preflight.js").read_text(encoding="utf-8")
    css = static.joinpath("mission-preflight.css").read_text(encoding="utf-8")
    assert "/api/missions/preflight" in js
    assert "1200" in js
    assert ".mission-preflight-result" in css

    state = DashboardState(TonmenConfig(workspace=tmp_path))
    payload = state.mission_preflight("localhost", _mission_policy({}))
    assert payload["target"] == "localhost"
    assert payload["policy"]["max_duration_seconds"] == 1200
