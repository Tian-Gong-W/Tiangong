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
        "/artifacts",
        "/settings",
    }


def test_module_workspace_assets_are_packaged_and_routed():
    static = resources.files("tonmen.dashboard.static")
    js = static.joinpath("module-pages.js").read_text(encoding="utf-8")
    css = static.joinpath("module-pages.css").read_text(encoding="utf-8")
    deck = static.joinpath("deck.js").read_text(encoding="utf-8")
    operator_css = static.joinpath("history-delete.css").read_text(encoding="utf-8")
    artifacts_js = static.joinpath("artifacts.js").read_text(encoding="utf-8")
    artifacts_css = static.joinpath("artifacts.css").read_text(encoding="utf-8")

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
    assert "candidate_capabilities" in deck
    assert "Evidence-driven replanning" in deck
    assert "const plannedSteps" not in deck
    assert ".operator-hub" in operator_css

    assert "/artifacts" in artifacts_js
    assert "/api/artifacts/inspect" in artifacts_js
    assert "STATIC ONLY" in artifacts_js
    assert "EXECUTION OFF" in artifacts_js
    assert "32 * 1024 * 1024" in artifacts_js
    assert "X-TONMEN-FILENAME" in artifacts_js
    assert "server" not in artifacts_js.lower() or "服务器路径" in artifacts_js
    assert ".artifact-workbench" in artifacts_css


def test_dashboard_detail_apis_expose_tools_guard_and_settings(tmp_path):
    config = TonmenConfig(workspace=tmp_path, config_path=tmp_path / "tonmen.toml")
    state = DashboardState(config)

    tools = state.tools()
    assert tools["count"] == 6
    assert {tool["name"] for tool in tools["tools"]} == {
        "nmap", "dns-intel", "httpx", "tls-intel", "crawler", "nuclei"
    }
    assert all("risk" in tool and "capabilities" in tool for tool in tools["tools"])
    crawler = next(tool for tool in tools["tools"] if tool["name"] == "crawler")
    assert crawler["available"] is True
    assert "endpoint.discover" in crawler["capabilities"]
    dns = next(tool for tool in tools["tools"] if tool["name"] == "dns-intel")
    tls = next(tool for tool in tools["tools"] if tool["name"] == "tls-intel")
    assert "dns.resolve" in dns["capabilities"]
    assert "certificate.inspect" in tls["capabilities"]

    guard = state.guard()
    assert guard["mode"] == "deny-by-default"
    assert guard["risk_levels"]
    assert any(rule["decision"] == "approval" for rule in guard["rules"])
    assert guard["audit"]["events"] == []

    settings = state.settings()
    assert settings["workspace"] == str(tmp_path)
    assert settings["console_loopback_only"] is True
    assert settings["allow_arbitrary_shell"] is False
    assert settings["artifact_upload_max_bytes"] == 32 * 1024 * 1024
    assert settings["artifact_execution_enabled"] is False


def test_dashboard_artifact_lifecycle_is_byte_based_static_only(tmp_path):
    config = TonmenConfig(workspace=tmp_path, config_path=tmp_path / "tonmen.toml")
    state = DashboardState(config)

    initial = state.artifacts()
    assert initial["count"] == 0
    assert initial["mode"] == "static-only"
    assert initial["execution_performed"] is False

    payload = state.inspect_artifact_bytes(b"MZ" + b"\x00" * 126, "demo.exe")
    artifact_id = payload["artifact_id"]
    assert payload["source_name"] == "demo.exe"
    assert payload["execution_performed"] is False
    assert payload["content_addressed"] is True

    listed = state.artifacts()
    assert listed["count"] == 1
    assert listed["artifacts"][0]["artifact_id"] == artifact_id

    detail = state.artifact(artifact_id)
    assert detail["integrity_verified"] is True
    assert detail["execution_performed"] is False

    deleted = state.delete_artifact(artifact_id)
    assert deleted == {"deleted": artifact_id, "remaining": 0}
    assert state.artifacts()["count"] == 0


def test_dashboard_plan_preview_exposes_seed_and_uncommitted_capability_pool(tmp_path):
    config = TonmenConfig(
        workspace=tmp_path,
        config_path=tmp_path / "tonmen.toml",
        allowed_targets=("localhost",),
    )
    state = DashboardState(config)

    preview = state.preview_plan("https://localhost")

    assert preview["planner"] == "AdaptiveMissionPlanner"
    assert preview["mode"] == "evidence-driven-adaptive"
    assert preview["executes"] is False
    assert preview["future_steps_committed"] is False
    assert [step["tool"] for step in preview["steps"]] == ["httpx"]
    assert [step["tool"] for step in preview["candidate_capabilities"]] == ["nmap", "httpx", "crawler", "nuclei"]
    assert preview["autonomy"] == {
        "committed_seed_steps": 1,
        "automatic_candidates": 3,
        "approval_candidates": 1,
        "next_approval_tool": "nuclei",
    }

    seed = preview["steps"][0]
    assert seed["argv"][0] == "httpx"
    assert seed["policy"]["decision"] == "allow"
    assert "ready" in seed["readiness"]
    assert seed["rationale"]

    crawler = preview["candidate_capabilities"][2]
    assert "argv" not in crawler
    assert crawler["parameters"]["max_pages"] == 25

    nuclei = preview["candidate_capabilities"][-1]
    assert nuclei["requires_approval"] is True
    assert nuclei["policy"]["decision"] == "require_approval"
    assert nuclei["risk"] == 3


def test_dashboard_host_preview_uses_network_seed(tmp_path):
    state = DashboardState(
        TonmenConfig(
            workspace=tmp_path,
            config_path=tmp_path / "tonmen.toml",
            allowed_targets=("localhost",),
        )
    )

    preview = state.preview_plan("localhost")

    assert [step["tool"] for step in preview["steps"]] == ["nmap"]
    assert preview["steps"][0]["target"] == "localhost"


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
