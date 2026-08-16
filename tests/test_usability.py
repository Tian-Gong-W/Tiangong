from __future__ import annotations

from pathlib import Path

from tonmen.core.config import DEFAULT_ALLOWED_TARGETS, TonmenConfig
from tonmen.core.runtime import TonmenRuntime
from tonmen.doctor import run_doctor
from tonmen.policy import TargetScope, validate_scope_rule


def test_config_roundtrip_persists_custom_scope(tmp_path):
    path = tmp_path / "tonmen.toml"
    config = TonmenConfig.default(path).with_allowed_target("app.example.test")
    config.save()

    loaded = TonmenConfig.load(path)

    assert loaded.workspace == (tmp_path / ".tonmen").resolve()
    assert set(DEFAULT_ALLOWED_TARGETS).issubset(loaded.allowed_targets)
    assert "app.example.test" in loaded.allowed_targets
    assert loaded.allow_arbitrary_shell is False


def test_config_cannot_remove_default_loopback_scope(tmp_path):
    config = TonmenConfig.default(tmp_path / "tonmen.toml")

    try:
        config.without_allowed_target("localhost")
    except ValueError as exc:
        assert "cannot be removed" in str(exc)
    else:
        raise AssertionError("built-in loopback scope must remain present")


def test_scope_rule_accepts_host_cidr_and_leading_wildcard():
    assert validate_scope_rule("App.Example.Test") == "app.example.test"
    assert validate_scope_rule("10.20.30.44/24") == "10.20.30.0/24"
    assert validate_scope_rule("*.Example.Test") == "*.example.test"

    scope = TargetScope(("10.20.30.0/24", "*.example.test"))
    assert scope.is_allowed("10.20.30.5")
    assert scope.is_allowed("api.example.test")
    assert not scope.is_allowed("example.test")


def test_scope_rule_rejects_shell_syntax():
    try:
        validate_scope_rule("example.test;whoami")
    except ValueError as exc:
        assert "forbidden" in str(exc)
    else:
        raise AssertionError("scope rule shell syntax must be rejected")


def test_doctor_reports_missing_external_tools(tmp_path):
    config = TonmenConfig(workspace=tmp_path, config_path=tmp_path / "tonmen.toml")
    paths = {"nmap": "/usr/bin/nmap", "httpx": None, "nuclei": "/usr/bin/nuclei"}

    report = run_doctor(config, which=lambda name: paths[name])

    assert report.ready is False
    by_name = {check.name: check for check in report.checks}
    assert by_name["nmap"].ok is True
    assert by_name["httpx"].ok is False
    assert by_name["nuclei"].ok is True


def test_status_reports_current_runtime_layers(tmp_path):
    runtime = TonmenRuntime.sentinel(TonmenConfig(workspace=Path(tmp_path)))

    status = runtime.status_text()

    assert "天機 Planner      ● Ready" in status
    assert "天鑑 Intelligence ● Ready" in status
    assert "天策 Reasoner     ● Ready" in status
    assert "天衡 Mission Loop ● Ready" in status
    assert "Not loaded" not in status
