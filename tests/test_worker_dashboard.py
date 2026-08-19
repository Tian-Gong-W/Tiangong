from __future__ import annotations

import json
from importlib import resources

from tonmen.core.config import TonmenConfig
from tonmen.dashboard import DashboardState
from tonmen.entry import _is_worker_invocation

_SECRET = "dashboard-worker-secret-0123456789-ABCDEFG"


def test_worker_fleet_assets_are_packaged():
    static = resources.files("tonmen.dashboard.static")
    html = static.joinpath("worker-fleet-page.html").read_text(encoding="utf-8")
    js = static.joinpath("worker-fleet-page.js").read_text(encoding="utf-8")
    css = static.joinpath("worker-fleet-page.css").read_text(encoding="utf-8")

    assert "天役" in html
    assert "Worker Fleet" in html
    assert "APPROVAL TOKEN" in html
    assert "/api/workers" in js
    assert "data-worker-probe" in js
    assert ".worker-grid" in css


def test_entry_routes_worker_without_changing_console_shape():
    assert _is_worker_invocation(["worker", "--id", "uae-1"])
    assert _is_worker_invocation(["--config", "worker.toml", "worker", "--id", "uae-1"])
    assert not _is_worker_invocation(["console", "--no-open"])
    assert not _is_worker_invocation(["status"])


def test_worker_fleet_status_is_side_effect_free_and_secret_safe(monkeypatch, tmp_path):
    monkeypatch.setenv(
        "TONMEN_WORKERS",
        "uae-1@http://127.0.0.1:8890#region=uae#tags=web,nuclei#secret_env=TONMEN_WORKER_SECRET_UAE1#weight=2",
    )
    monkeypatch.setenv("TONMEN_WORKER_SECRET_UAE1", _SECRET)
    monkeypatch.delenv("TONMEN_EXECUTION_MODE", raising=False)

    state = DashboardState(TonmenConfig(workspace=tmp_path))
    payload = state.worker_fleet()
    rendered = json.dumps(payload)

    assert payload["execution_mode"] == "local"
    assert len(payload["workers"]) == 1
    worker = payload["workers"][0]
    assert worker["id"] == "uae-1"
    assert worker["region"] == "uae"
    assert worker["secret_configured"] is True
    assert worker["last_probe"] is None
    assert _SECRET not in rendered
    assert payload["privacy"]["secret_values_exposed"] is False
    assert payload["privacy"]["approval_tokens_sent"] is False
    assert payload["privacy"]["raw_shell_sent"] is False
    assert payload["privacy"]["raw_argv_sent"] is False


def test_worker_probe_response_is_sanitized(monkeypatch, tmp_path):
    monkeypatch.setenv(
        "TONMEN_WORKERS",
        "uae-1@http://127.0.0.1:8890#region=uae#tags=web#secret_env=TONMEN_WORKER_SECRET_UAE1",
    )
    monkeypatch.setenv("TONMEN_WORKER_SECRET_UAE1", _SECRET)
    monkeypatch.delenv("TONMEN_EXECUTION_MODE", raising=False)

    def fake_health(self, spec, timeout=5):
        return {
            "ok": True,
            "worker": {"id": "uae-1", "region": "uae", "tags": ["web"]},
            "tools": {
                "httpx": {"ready": True, "code": "ready", "secret": _SECRET},
                "nmap": {"ready": False, "code": "missing_binary"},
            },
            "ready_tools": 1,
            "total_tools": 2,
            "governance": {
                "local_scope_check": True,
                "local_policy_check": True,
                "approval_token_received": False,
                "argv_received": False,
            },
        }

    monkeypatch.setattr("tonmen.dashboard.provider_server.WorkerHTTPTransport.health", fake_health)
    state = DashboardState(TonmenConfig(workspace=tmp_path))
    payload = state.probe_worker("uae-1")
    rendered = json.dumps(payload)

    assert payload["ready"] is True
    assert payload["ready_tools"] == 1
    assert payload["tools"]["httpx"] == {"ready": True, "code": "ready"}
    assert _SECRET not in rendered
