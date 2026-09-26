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


def test_scope_rule_accepts_host_cidr_leading_wildcard_and_http_url():
    assert validate_scope_rule("App.Example.Test") == "app.example.test"
    assert validate_scope_rule("10.20.30.44/24") == "10.20.30.0/24"
    assert validate_scope_rule("*.Example.Test") == "*.example.test"
    assert validate_scope_rule("http://165252.cc") == "165252.cc"
    assert validate_scope_rule("https://App.Example.Test:8443/login?q=1") == "app.example.test"
    assert validate_scope_rule("http://[::1]:8080/status") == "::1/128"

    scope = TargetScope(("10.20.30.0/24", "*.example.test"))
    assert scope.is_allowed("10.20.30.5")
    assert scope.is_allowed("api.example.test")
    assert not scope.is_allowed("example.test")


def test_scope_rule_rejects_shell_syntax_and_unsafe_url_forms():
    try:
        validate_scope_rule("example.test;whoami")
    except ValueError as exc:
        assert "forbidden" in str(exc)
    else:
        raise AssertionError("scope rule shell syntax must be rejected")

    try:
        validate_scope_rule("ftp://example.test/file")
    except ValueError as exc:
        assert "http or https" in str(exc)
    else:
        raise AssertionError("non-HTTP scope URLs must be rejected")

    try:
        validate_scope_rule("https://user:pass@example.test/private")
    except ValueError as exc:
        assert "credentials" in str(exc)
    else:
        raise AssertionError("scope URLs with credentials must be rejected")


def test_doctor_reports_missing_external_tools(tmp_path):
    config = TonmenConfig(workspace=tmp_path, config_path=tmp_path / "tonmen.toml")
    paths = {"nmap": "/usr/bin/nmap", "httpx": None, "nuclei": "/usr/bin/nuclei"}
    templates = tmp_path / "nuclei-templates" / "http"
    templates.mkdir(parents=True)
    (templates / "demo.yaml").write_text("id: demo\n", encoding="utf-8")

    report = run_doctor(config, which=lambda name: paths[name], home=tmp_path)

    assert report.ready is False
    by_name = {check.name: check for check in report.checks}
    assert by_name["nmap"].ok is True
    assert by_name["httpx"].ok is False
    assert by_name["nuclei-binary"].ok is True
    assert by_name["nuclei-templates"].ok is True
    assert by_name["nuclei"].ok is True


def test_doctor_blocks_nuclei_when_templates_are_missing(tmp_path):
    config = TonmenConfig(workspace=tmp_path, config_path=tmp_path / "tonmen.toml")
    paths = {"nmap": "/usr/bin/nmap", "httpx": "/usr/bin/httpx", "nuclei": "/usr/bin/nuclei"}

    report = run_doctor(config, which=lambda name: paths[name], home=tmp_path)
    by_name = {check.name: check for check in report.checks}

    assert report.ready is False
    assert by_name["nuclei-binary"].ok is True
    assert by_name["nuclei-templates"].ok is False
    assert by_name["nuclei-templates"].code == "missing_templates"
    assert "nuclei -ut" in (by_name["nuclei-templates"].remediation or "")
    assert by_name["nuclei"].ok is False
    assert by_name["nuclei"].code == "missing_templates"


def test_status_reports_current_runtime_layers(tmp_path):
    runtime = TonmenRuntime.sentinel(TonmenConfig(workspace=Path(tmp_path)))

    status = runtime.status_text()

    assert "天機 Planner      ● Ready" in status
    assert "天鑑 Intelligence ● Ready" in status
    assert "天策 Reasoner     ● Ready" in status
    assert "天衡 Mission Loop ● Ready" in status
    assert "Not loaded" not in status
