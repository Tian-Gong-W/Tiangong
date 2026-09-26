from __future__ import annotations

from importlib import resources

import pytest

from tonmen.chronicle import ChronicleStore
from tonmen.core.config import TonmenConfig
from tonmen.dashboard.server import _STATIC_TYPES, DashboardState
from tonmen.missions import MissionPlan, MissionRun, MissionRunState


def _persist(store: ChronicleStore, state: MissionRunState, target: str = "example.test"):
    plan = MissionPlan.create(target, [])
    run = MissionRun.create(plan)
    if state in {MissionRunState.SUCCEEDED, MissionRunState.FAILED, MissionRunState.DENIED}:
        run.finish(state)
    else:
        run.state = state
    store.save(plan, run)
    return plan, run


def test_chronicle_delete_removes_only_requested_file(tmp_path):
    store = ChronicleStore(tmp_path)
    _, first = _persist(store, MissionRunState.FAILED)
    _, second = _persist(store, MissionRunState.SUCCEEDED)

    assert store.delete(first.id) is True
    assert store.delete(first.id) is False
    assert [entry.run_id for entry in store.list()] == [second.id]

    with pytest.raises(ValueError, match="invalid mission run id"):
        store.delete("../audit.jsonl")


def test_dashboard_deletes_terminal_mission_and_keeps_audit(tmp_path):
    state = DashboardState(TonmenConfig(workspace=tmp_path, config_path=tmp_path / "tonmen.toml"))
    _, run = _persist(state.chronicle, MissionRunState.FAILED, "165252.cc")

    payload = state.delete_mission(run.id)

    assert payload["deleted"] == run.id
    assert payload["remaining"] == 0
    with pytest.raises(FileNotFoundError):
        state.chronicle.load(run.id)

    audit = state.audit(20)["events"]
    assert audit[-1]["action"] == "mission.delete"
    assert audit[-1]["decision"] == "delete"
    assert run.id in audit[-1]["message"]

    events = state.event_stream(0, timeout=0, limit=20)["events"]
    deleted = [event for event in events if event["type"] == "mission.deleted"]
    assert deleted and deleted[-1]["data"]["mission_id"] == run.id


def test_dashboard_refuses_to_delete_active_or_waiting_missions(tmp_path):
    state = DashboardState(TonmenConfig(workspace=tmp_path, config_path=tmp_path / "tonmen.toml"))
    _, running = _persist(state.chronicle, MissionRunState.RUNNING)
    _, waiting = _persist(state.chronicle, MissionRunState.WAITING_APPROVAL)

    with pytest.raises(ValueError, match="completed, failed or denied"):
        state.delete_mission(running.id)
    with pytest.raises(ValueError, match="completed, failed or denied"):
        state.delete_mission(waiting.id)

    assert {entry.run_id for entry in state.chronicle.list()} == {running.id, waiting.id}


def test_cleanup_removes_only_terminal_history(tmp_path):
    state = DashboardState(TonmenConfig(workspace=tmp_path, config_path=tmp_path / "tonmen.toml"))
    terminal = [
        _persist(state.chronicle, MissionRunState.FAILED)[1],
        _persist(state.chronicle, MissionRunState.SUCCEEDED)[1],
        _persist(state.chronicle, MissionRunState.DENIED)[1],
    ]
    active = [
        _persist(state.chronicle, MissionRunState.RUNNING)[1],
        _persist(state.chronicle, MissionRunState.WAITING_APPROVAL)[1],
    ]

    payload = state.cleanup_terminal_missions()

    assert payload["count"] == 3
    assert set(payload["deleted"]) == {run.id for run in terminal}
    assert {entry.run_id for entry in state.chronicle.list()} == {run.id for run in active}


def test_console_packages_history_delete_controls_and_csrf_calls():
    static = resources.files("tonmen.dashboard.static")
    script = static.joinpath("history-delete.js").read_text(encoding="utf-8")
    css = static.joinpath("history-delete.css").read_text(encoding="utf-8")

    assert _STATIC_TYPES["history-delete.js"].startswith("text/javascript")
    assert _STATIC_TYPES["history-delete.css"].startswith("text/css")
    assert "/api/missions/cleanup" in script
    assert "/delete`" in script
    assert "X-TONMEN-CSRF" in script
    assert "Audit 审计日志保留" in script
    assert "data-delete-selected-mission" in script
    assert "data-cleanup-terminal-missions" in script
    assert ".mission-history-actions" in css
