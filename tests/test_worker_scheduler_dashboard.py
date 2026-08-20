from __future__ import annotations

import json
from importlib import resources

from tonmen.core.config import TonmenConfig
from tonmen.dashboard import DashboardState

_SECRET = "dashboard-scheduler-secret-0123456789-ABCDEFG"


def test_worker_fleet_js_exposes_capacity_queue_and_drain_controls():
    js = resources.files("tonmen.dashboard.static").joinpath("worker-fleet-page.js").read_text(encoding="utf-8")
    assert "Queue depth" in js
    assert "max_concurrency" in js
    assert "data-worker-drain" in js
    assert "/drain" not in js  # action is composed dynamically; no secret-bearing URL templates
    assert 'const action = draining ? "activate" : "drain"' in js


def test_worker_fleet_scheduler_status_and_drain_are_runtime_only(monkeypatch, tmp_path):
    monkeypatch.setenv("TONMEN_EXECUTION_MODE", "worker")
    monkeypatch.setenv(
        "TONMEN_WORKERS",
        "uae-1@http://127.0.0.1:8890#region=uae#tags=web#secret_env=TONMEN_WORKER_SECRET_UAE1#concurrency=3",
    )
    monkeypatch.setenv("TONMEN_WORKER_SECRET_UAE1", _SECRET)
    state = DashboardState(TonmenConfig(workspace=tmp_path))

    before = state.worker_fleet()
    assert before["execution_mode"] == "worker"
    assert before["scheduler"]["queue_depth"] == 0
    assert before["workers"][0]["scheduler"]["max_concurrency"] == 3
    assert before["workers"][0]["scheduler"]["draining"] is False

    changed = state.set_worker_drain("uae-1", True)
    assert changed["draining"] is True
    after = state.worker_fleet()
    assert after["workers"][0]["draining"] is True
    assert after["workers"][0]["scheduler"]["draining"] is True
    assert _SECRET not in json.dumps(after)

    resumed = state.set_worker_drain("uae-1", False)
    assert resumed["draining"] is False


def test_cached_worker_health_is_sanitized_before_fleet_exposure(monkeypatch, tmp_path):
    monkeypatch.setenv("TONMEN_EXECUTION_MODE", "worker")
    monkeypatch.setenv(
        "TONMEN_WORKERS",
        "uae-1@http://127.0.0.1:8890#secret_env=TONMEN_WORKER_SECRET_UAE1#concurrency=2",
    )
    monkeypatch.setenv("TONMEN_WORKER_SECRET_UAE1", _SECRET)
    state = DashboardState(TonmenConfig(workspace=tmp_path))
    state.runtime.workers.record_health(
        "uae-1",
        {
            "ok": True,
            "worker": {"id": "uae-1", "region": "uae", "tags": ["web"], "credential": _SECRET},
            "tools": {"httpx": {"ready": True, "code": "ready", "private": _SECRET}},
            "capacity": {"inflight": 1, "max_concurrency": 2, "available_slots": 1, "accepting_jobs": True, "secret": _SECRET},
            "unexpected": _SECRET,
        },
    )
    rendered = json.dumps(state.worker_fleet())
    assert _SECRET not in rendered
