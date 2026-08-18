from __future__ import annotations

import os

from tonmen.core.config import TonmenConfig
from tonmen.doctor import run_doctor
from tonmen.execution import ToolExecutor
from tonmen.policy import PolicyEngine
from tonmen.tools import ToolRegistry, ToolRequest
from tonmen.tools.adapters import HttpxAdapter
from tonmen.tools.binary_identity import resolve_projectdiscovery_httpx


def _write_executable(path, body: str) -> None:
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)


def _shadowed_pair(tmp_path):
    bad_dir = tmp_path / "bad"
    good_dir = tmp_path / "good"
    bad_dir.mkdir()
    good_dir.mkdir()
    bad = bad_dir / "httpx"
    good = good_dir / "httpx"
    _write_executable(bad, "#!/bin/sh\necho 'Python HTTP client CLI --help --version'\n")
    _write_executable(
        good,
        "#!/bin/sh\n"
        "if [ \"$1\" = \"-h\" ]; then\n"
        "  echo 'ProjectDiscovery httpx -u -silent -status-code -tech-detect -timeout'\n"
        "else\n"
        "  echo 'https://example.test [200] [demo] [server]'\n"
        "fi\n",
    )
    return bad, good, f"{bad_dir}{os.pathsep}{good_dir}"


def test_httpx_resolver_skips_incompatible_earlier_path_candidate(tmp_path):
    bad, good, path_value = _shadowed_pair(tmp_path)

    resolution = resolve_projectdiscovery_httpx(environ={"PATH": path_value})

    assert resolution.ready is True
    assert resolution.path == str(good.resolve())
    assert str(bad.resolve()) in resolution.rejected
    assert "ignored incompatible earlier PATH candidate" in resolution.detail


def test_httpx_resolver_rejects_wrong_identity_when_no_compatible_candidate(tmp_path):
    bad_dir = tmp_path / "bad"
    bad_dir.mkdir()
    bad = bad_dir / "httpx"
    _write_executable(bad, "#!/bin/sh\necho 'Python HTTP client CLI'\n")

    resolution = resolve_projectdiscovery_httpx(environ={"PATH": str(bad_dir)})

    assert resolution.ready is False
    assert resolution.code == "wrong_binary_identity"
    assert str(bad.resolve()) in resolution.rejected


def test_doctor_reports_verified_later_httpx_candidate(tmp_path):
    bad, good, path_value = _shadowed_pair(tmp_path)
    templates = tmp_path / "nuclei-templates"
    templates.mkdir()
    (templates / "demo.yaml").write_text("id: demo\n", encoding="utf-8")

    def fake_which(name: str):
        return f"/fake/{name}" if name in {"nmap", "nuclei"} else None

    report = run_doctor(
        TonmenConfig(workspace=tmp_path / "workspace"),
        which=fake_which,
        environ={"PATH": path_value},
        home=tmp_path,
    )
    check = next(item for item in report.checks if item.name == "httpx")

    assert check.ok is True
    assert check.metadata["identity_verified"] is True
    assert check.metadata["path"] == str(good.resolve())
    assert str(bad.resolve()) in check.metadata["rejected"]


def test_local_executor_uses_verified_absolute_httpx_path(monkeypatch, tmp_path):
    bad, good, path_value = _shadowed_pair(tmp_path)
    monkeypatch.setenv("PATH", path_value)
    registry = ToolRegistry()
    registry.register(HttpxAdapter())

    outcome = ToolExecutor(registry, PolicyEngine()).execute(
        ToolRequest(tool="httpx", target="https://example.test")
    )

    assert outcome.result.success is True
    assert outcome.evidence.argv[0] == str(good.resolve())
    assert outcome.evidence.argv[0] != str(bad.resolve())
