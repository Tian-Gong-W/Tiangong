from __future__ import annotations

import json
from importlib import resources

from tonmen.core.config import TonmenConfig
from tonmen.dashboard.server import _APP_ROUTES, DashboardState


def test_console_exposes_full_module_route_map():
    assert _APP_ROUTES == {
        "/",
        "/missions",
        "/scope",
        "/guard",
        "/tools",
        "/intelligence",
        "/reasoner",
        "/lead",
        "/loop",
        "/chronicle",
        "/approval",
        "/settings",
    }


def test_module_workspace_assets_are_packaged_and_routed():
    static = resources.files("tonmen.dashboard.static")
    js = static.joinpath("module-pages.js").read_text(encoding="utf-8")
    css = static.joinpath("module-pages.css").read_text(encoding="utf-8")

    for route in (
        "/missions",
        "/scope",
        "/guard",
        "/tools",
        "/intelligence",
        "/reasoner",
        "/lead",
        "/loop",
        "/chronicle",
        "/approval",
        "/settings",
    ):
        assert route in js

    assert "setInterval" in js
    assert "2500" in js
    assert "执行内容" in js
    assert "stdout" in js
    assert "stderr" in js
    assert ".module-page-root" in css
    assert ".terminal" in css


def test_dashboard_detail_apis_expose_tools_guard_and_settings(tmp_path):
    config = TonmenConfig(workspace=tmp_path, config_path=tmp_path / "tonmen.toml")
    state = DashboardState(config)

    tools = state.tools()
    assert tools["count"] == 3
    assert {tool["name"] for tool in tools["tools"]} == {"nmap", "httpx", "nuclei"}
    assert all("risk" in tool and "capabilities" in tool for tool in tools["tools"])

    guard = state.guard()
    assert guard["mode"] == "deny-by-default"
    assert guard["risk_levels"]
    assert any(rule["decision"] == "approval" for rule in guard["rules"])
    assert guard["audit"]["events"] == []

    settings = state.settings()
    assert settings["workspace"] == str(tmp_path)
    assert settings["console_loopback_only"] is True
    assert settings["allow_arbitrary_shell"] is False


def test_live_audit_tail_is_readable_without_exposing_tokens(tmp_path):
    config = TonmenConfig(workspace=tmp_path, config_path=tmp_path / "tonmen.toml")
    state = DashboardState(config)
    audit_path = tmp_path / "audit.jsonl"
    audit_path.write_text(
        json.dumps(
            {
                "timestamp": "2026-08-16T12:00:00+00:00",
                "action": "tool.execute",
                "tool": "nmap",
                "target": "localhost",
                "decision": "allow",
                "message": "execution completed",
                "evidence_id": "e-1",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    payload = state.audit(20)
    assert payload["events"][0]["tool"] == "nmap"
    assert payload["events"][0]["decision"] == "allow"
    assert "token" not in payload["events"][0]
