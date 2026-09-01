from __future__ import annotations

import json
import subprocess
import threading
import time
from importlib import resources

from tonmen.agents import MissionPlanner
from tonmen.ai.secrets import public_secret_status
from tonmen.core.config import TonmenConfig
from tonmen.dashboard import DashboardState
from tonmen.dashboard.usability_server import _friendly_error
from tonmen.jobs import JobManager
from tonmen.loop import MissionLoop, MissionLoopPolicy
from tonmen.missions import MissionRunState, StepExecutionState
from tonmen.tools import ToolReadiness


def _ready():
    return ToolReadiness(True, "ready", "test ready")


def _isolate_ai(monkeypatch, tmp_path):
    monkeypatch.setenv("TONMEN_AI_SECRETS_FILE", str(tmp_path / "secrets.json"))
    monkeypatch.setenv("TONMEN_AI_SETTINGS_FILE", str(tmp_path / "ai-settings.json"))
    for name in (
        "TONMEN_AI_PROVIDER", "TONMEN_AI_MODEL", "TONMEN_AI_POOL",
        "OPENAI_API_KEY", "DEEPSEEK_API_KEY", "MISTRAL_API_KEY",
    ):
        monkeypatch.delenv(name, raising=False)


def test_web_saved_provider_key_is_persistent_secret_safe_and_live(monkeypatch, tmp_path):
    _isolate_ai(monkeypatch, tmp_path)
    state = DashboardState(TonmenConfig(workspace=tmp_path / "workspace"))
    secret = "deepseek-local-secret-never-render-this-value"

    result = state.save_provider_key("deepseek", secret)
    hub = state.provider_hub()
    rendered = json.dumps(hub)
    provider = next(item for item in hub["providers"] if item["id"] == "deepseek")

    assert result["configured"] is True
    assert result["source"] == "local_store"
    assert secret not in rendered
    assert provider["key_configured"] is True
    assert provider["local_secret"]["persisted_by_tonmen"] is True
    assert public_secret_status("DEEPSEEK_API_KEY")["source"] == "local_store"
    assert (tmp_path / "secrets.json").exists()
    assert (tmp_path / "secrets.json").stat().st_mode & 0o777 == 0o600

    cleared = state.clear_provider_key("deepseek")
    assert cleared["configured"] is False
    assert public_secret_status("DEEPSEEK_API_KEY")["configured"] is False


def test_web_ai_settings_apply_without_restart_and_do_not_expose_secret(monkeypatch, tmp_path):
    _isolate_ai(monkeypatch, tmp_path)
    state = DashboardState(TonmenConfig(workspace=tmp_path / "workspace"))

    state.save_provider_key("openai", "openai-secret-never-public")
    result = state.update_ai_configuration({"lead_enabled": True, "lead_model": "gpt-5.6", "pool": ["auto"]})
    hub = state.provider_hub()
    lead = state.lead_ai()

    assert result["applied_without_restart"] is True
    assert result["settings"]["lead_provider"] == "openai"
    assert result["settings"]["pool"] == ["auto"]
    assert lead["config"]["provider"] == "openai"
    assert lead["config"]["key_configured"] is True
    assert "openai-secret-never-public" not in json.dumps({"hub": hub, "lead": lead})


def test_approval_returns_immediately_suppresses_duplicates_and_finishes_in_background(monkeypatch, tmp_path):
    _isolate_ai(monkeypatch, tmp_path)
    state = DashboardState(TonmenConfig(workspace=tmp_path, allowed_targets=("localhost",)))
    runtime = state.runtime
    for adapter in runtime.registry:
        monkeypatch.setattr(adapter, "readiness", _ready)

    release = threading.Event()
    nuclei_started = threading.Event()
    outputs = {
        "nmap": "Nmap scan report for localhost\nHost is up.\n80/tcp open http\n",
        "httpx": "https://localhost [200] [Welcome] [nginx]\n",
        "nuclei": "",
    }

    def runner(argv, **kwargs):
        if argv[0] == "nuclei":
            nuclei_started.set()
            release.wait(timeout=3)
        return subprocess.CompletedProcess(argv, 0, stdout=outputs.get(argv[0], ""), stderr="")

    runtime.executor._runner = runner
    runtime.jobs = JobManager(runtime.executor)
    plan = MissionPlanner(runtime).plan("localhost")
    first = MissionLoop(runtime, MissionLoopPolicy(), checkpoint=state._checkpoint).run(plan)
    assert first.run.state is MissionRunState.WAITING_APPROVAL

    started = time.monotonic()
    accepted = state.approve_mission(first.run.id)
    elapsed = time.monotonic() - started
    duplicate = state.approve_mission(first.run.id)

    assert elapsed < 0.5
    assert accepted["status"] in {"accepted", "running"}
    assert accepted["state"] == MissionRunState.RUNNING.value
    assert accepted["approval_token_exposed"] is False
    assert duplicate["duplicate_suppressed"] is True
    assert duplicate["status"] in {"accepted", "running"}

    assert nuclei_started.wait(timeout=1), "approved validation did not start in the background"
    _, executing_run = state.chronicle.load(first.run.id)
    assert executing_run.state is MissionRunState.RUNNING
    nuclei_execution = next(step for step in executing_run.steps if step.tool == "nuclei")
    assert nuclei_execution.state is StepExecutionState.RUNNING

    release.set()
    deadline = time.monotonic() + 4
    status = state.approval_status(first.run.id)
    while status["status"] not in {"completed", "failed"} and time.monotonic() < deadline:
        time.sleep(0.02)
        status = state.approval_status(first.run.id)

    assert status["status"] == "completed"
    _, stored_run = state.chronicle.load(first.run.id)
    assert stored_run.state is MissionRunState.SUCCEEDED


def test_friendly_errors_explain_next_action():
    message, action = _friendly_error("mission is not waiting for approval")
    assert "刷新" in message
    assert action == "刷新任务"
    message, action = _friendly_error("execution timed out after 900 seconds")
    assert "900" in message
    assert "重新批准" in (action or "")


def test_usability_assets_are_packaged():
    static = resources.files("tonmen.dashboard.static")
    main_js = static.joinpath("console-usability.js").read_text(encoding="utf-8")
    easy_js = static.joinpath("provider-easy-setup.js").read_text(encoding="utf-8")
    assert "再次点击确认" in main_js
    assert "批准并继续" in main_js
    assert "/approval-status" in main_js
    assert "/api/ai/config" in easy_js
    assert "粘贴 API Key" in easy_js
    assert "AI 快速配置" in easy_js