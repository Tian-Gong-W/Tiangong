from __future__ import annotations

import json
from importlib import resources

import pytest

from tonmen.agents import MissionPlanningDenied
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
        "/loop",
        "/chronicle",
        "/approval",
        "/settings",
    }


def test_module_workspace_assets_are_packaged_and_routed():
    static = resources.files("tonmen.dashboard.static")
    js = static.joinpath("module-pages.js").read_text(encoding="utf-8")
    css = static.joinpath("module-pages.css").read_text(encoding="utf-8")
    deck = static.joinpath("deck.js").read_text(encoding="utf-8")
    operator_css = static.joinpath("history-delete.css").read_text(encoding="utf-8")

    for route in (
        "/missions",
        "/scope",
        "/guard",
        "/tools",
        "/intelligence",
        "/reasoner",
        "/loop",
        "/chronicle",
        "/approval",
        "/settings",
    ):
        assert route in js

    assert "setInterval" in js
    assert "2500" in js
    assert "Execution Content" in js
    assert "stdout" in js
    assert "stderr" in js
    assert ".module-page-root" in css
    assert ".terminal" in css
    assert "生成测试计划" in deck
    assert "实际执行清单" in deck
    assert "记录 / 删除" in deck
    assert "/api/plans/preview" in deck
    assert "const plannedSteps" not in deck
    assert ".operator-hub" in operator_css


def test_dashboard_detail_apis_expose_tools_guard_and_settings(tmp_path):
    config = TonmenConfig(workspace=tmp_path, config_path=tmp_path / "tonmen.toml")
    state = DashboardState(config)

    tools = state.tools()
    assert tools["count"] == 4
    assert {tool["name"] for tool in tools["tools"]} == {"nmap", "httpx", "crawler", "nuclei"}
    assert all("risk" in tool and "capabilities" in tool for tool in tools["tools"])
    crawler = next(tool for tool in tools["tools"] if tool["name"] == "crawler")
    assert crawler["available"] is True
    assert "endpoint.discover" in crawler["capabilities"]

    guard = state.guard()
    assert guard["mode"] == "deny-by-default"
    assert guard["risk_levels"]
    assert any(rule["decision"] == "approval" for rule in guard["rules"])
    assert guard["audit"]["events"] == []

    settings = state.settings()
    assert settings["workspace"] == str(tmp_path)
    assert settings["console_loopback_only"] is True
    assert settings["allow_arbitrary_shell"] is False


def test_dashboard_plan_preview_comes_from_governed_planner(tmp_path):
    config = TonmenConfig(
        workspace=tmp_path,
        config_path=tmp_path / "tonmen.toml",
        allowed_targets=("localhost",),
    )
    state = DashboardState(config)

    preview = state.preview_plan("https://localhost")

    assert preview["planner"] == "MissionPlanner"
    assert preview["mode"] == "deterministic-governed"
    assert preview["executes"] is False
    assert [step["tool"] for step in preview["steps"]] == ["nmap", "httpx", "crawler", "nuclei"]
    assert preview["autonomy"] == {
        "automatic_steps": 3,
        "approval_steps": 1,
        "next_approval_tool": "nuclei",
    }

    for step in preview["steps"]:
        assert step["argv"]
        assert step["policy"]["decision"] in {"allow", "require_approval"}
        assert "ready" in step["readiness"]
        assert step["rationale"]

    crawler = preview["steps"][2]
    assert crawler["argv"][1:3] == ["-m", "tonmen.tools.runners.crawler"]
    assert crawler["parameters"]["max_pages"] == 25

    nuclei = preview["steps"][-1]
    assert nuclei["requires_approval"] is True
    assert nuclei["policy"]["decision"] == "require_approval"
    assert nuclei["risk"] == 3


def test_dashboard_plan_preview_rejects_out_of_scope_target(tmp_path):
    state = DashboardState(
        TonmenConfig(
            workspace=tmp_path,
            config_path=tmp_path / "tonmen.toml",
            allowed_targets=("localhost",),
        )
    )

    with pytest.raises(MissionPlanningDenied, match="authorized scope"):
        state.preview_plan("https://example.com")


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
