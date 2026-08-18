from __future__ import annotations

import pytest

from tonmen.core.config import TonmenConfig
from tonmen.dashboard.server import DashboardState
from tonmen.missions import MissionPlan, MissionRun, MissionRunState, MissionStep, StepExecutionState
from tonmen.tools import RiskLevel, ToolReadiness


def _waiting_nuclei_plan_and_run():
    step = MissionStep.create(
        tool="nuclei",
        target="localhost",
        parameters={"severity": ("medium", "high"), "rate_limit": 10, "timeout": 10},
        risk=int(RiskLevel.VALIDATION),
        requires_approval=True,
        rationale="Validate only after explicit approval.",
    )
    plan = MissionPlan.create("localhost", [step])
    run = MissionRun.create(plan)
    run.state = MissionRunState.WAITING_APPROVAL
    run.steps[0].state = StepExecutionState.WAITING_APPROVAL
    run.steps[0].error = "explicit approval grant required"
    return plan, run


def test_dashboard_tools_expose_structured_readiness(monkeypatch, tmp_path):
    state = DashboardState(TonmenConfig(workspace=tmp_path, allowed_targets=("localhost",)))
    for adapter in state.runtime.registry:
        monkeypatch.setattr(adapter, "readiness", lambda: ToolReadiness(True, "ready", "test ready"))

    payload = state.tools()

    assert payload["count"] == 7
    assert payload["ready"] == 7
    assert all(tool["available"] is True for tool in payload["tools"])
    assert all(tool["readiness"]["code"] == "ready" for tool in payload["tools"])


def test_registry_status_reports_real_ready_count(monkeypatch, tmp_path):
    state = DashboardState(TonmenConfig(workspace=tmp_path, allowed_targets=("localhost",)))
    adapters = list(state.runtime.registry)
    assert [adapter.spec.name for adapter in adapters] == [
        "nmap", "dns-intel", "httpx", "tls-intel", "api-intel", "crawler", "nuclei"
    ]
    for adapter in adapters[:6]:
        monkeypatch.setattr(adapter, "readiness", lambda: ToolReadiness(True, "ready", "ready"))
    monkeypatch.setattr(adapters[6], "readiness", lambda: ToolReadiness(False, "missing_templates", "templates missing"))

    payload = state.status()
    registry = next(item for item in payload["components"] if item["id"] == "registry")

    assert registry["state"] == "6/7 Tools Ready"
    assert registry["tone"] == "amber"


def test_dashboard_refuses_approval_before_issuing_grant_when_tool_is_blocked(monkeypatch, tmp_path):
    state = DashboardState(TonmenConfig(workspace=tmp_path, allowed_targets=("localhost",)))
    plan, run = _waiting_nuclei_plan_and_run()
    state.chronicle.save(plan, run)
    adapter = state.runtime.registry.get("nuclei")
    monkeypatch.setattr(
        adapter,
        "readiness",
        lambda: ToolReadiness(
            False,
            "missing_templates",
            "Nuclei templates are missing",
            remediation="Run `nuclei -ut`.",
        ),
    )

    with pytest.raises(ValueError, match="preflight blocked"):
        state.approve_mission(run.id)

    assert state.runtime.approvals._grants == {}
    _, persisted = state.chronicle.load(run.id)
    assert persisted.state is MissionRunState.WAITING_APPROVAL
    assert persisted.steps[0].state is StepExecutionState.WAITING_APPROVAL


def test_console_readiness_ui_disables_blocked_approval():
    from importlib import resources

    js = resources.files("tonmen.dashboard.static").joinpath("events.js").read_text(encoding="utf-8")
    css = resources.files("tonmen.dashboard.static").joinpath("events.css").read_text(encoding="utf-8")

    assert "PRE-FLIGHT BLOCKED" in js
    assert "环境未就绪 · 无法批准执行" in js
    assert "nuclei -ut" in js
    assert "EVENT STREAM · 2.5s fallback" in js
    assert ".approval-preflight-block" in css
    assert "button[disabled]" in css
