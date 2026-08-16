from __future__ import annotations

from importlib import resources

import pytest

from tonmen.core.config import TonmenConfig
from tonmen.dashboard import DashboardState, validate_console_host
from tonmen.entry import _is_console_invocation


def test_console_is_loopback_only():
    assert validate_console_host("127.0.0.1") == "127.0.0.1"
    assert validate_console_host("localhost") == "localhost"
    assert validate_console_host("::1") == "::1"
    with pytest.raises(ValueError, match="loopback"):
        validate_console_host("0.0.0.0")
    with pytest.raises(ValueError, match="loopback"):
        validate_console_host("192.0.2.10")


def test_dashboard_assets_are_packaged():
    static = resources.files("tonmen.dashboard.static")
    assert "雲頂天宮" in static.joinpath("index.html").read_text(encoding="utf-8")
    assert "Evidence Graph" in static.joinpath("index.html").read_text(encoding="utf-8")
    assert "--cyan" in static.joinpath("app.css").read_text(encoding="utf-8")
    app_js = static.joinpath("app.js").read_text(encoding="utf-8")
    assert "X-TONMEN-CSRF" in app_js
    assert "▶ 執行任務" in app_js
    assert "查看原始證據" in app_js
    assert "無法載入任務詳情" in app_js


def test_dashboard_scope_uses_project_config(tmp_path):
    path = tmp_path / "tonmen.toml"
    config = TonmenConfig.default(path)
    config.save(path)
    state = DashboardState(TonmenConfig.load(path))
    updated = state.add_scope("app.example.test")
    assert any(item["rule"] == "app.example.test" for item in updated["allowed"])
    assert "app.example.test" in TonmenConfig.load(path).allowed_targets
    updated = state.remove_scope("app.example.test")
    assert all(item["rule"] != "app.example.test" for item in updated["allowed"])
    assert "app.example.test" not in TonmenConfig.load(path).allowed_targets


def test_default_loopback_scope_cannot_be_removed_from_dashboard(tmp_path):
    path = tmp_path / "tonmen.toml"
    config = TonmenConfig.default(path)
    config.save(path)
    state = DashboardState(TonmenConfig.load(path))
    with pytest.raises(ValueError, match="default loopback"):
        state.remove_scope("localhost")


def test_entry_routes_console_without_changing_legacy_cli_shape():
    assert _is_console_invocation(["console", "--no-open"])
    assert _is_console_invocation(["--config", "project.toml", "console", "--no-open"])
    assert not _is_console_invocation(["status"])
    assert not _is_console_invocation(["--config", "project.toml", "doctor"])


def test_dashboard_status_exposes_current_runtime_layers(tmp_path):
    config = TonmenConfig(workspace=tmp_path, config_path=tmp_path / "tonmen.toml")
    state = DashboardState(config)
    payload = state.status()
    names = {(item["zh"], item["en"]) for item in payload["components"]}
    assert ("天鑑", "Intelligence") in names
    assert ("天策", "Reasoner") in names
    assert ("天衡", "Mission Loop") in names
    assert payload["version"]
