from __future__ import annotations

import os

from tonmen.tools.binary_identity import resolve_projectdiscovery_httpx


def _write_executable(path, body: str) -> None:
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)


def test_httpx_resolver_skips_incompatible_earlier_path_candidate(tmp_path):
    bad_dir = tmp_path / "bad"
    good_dir = tmp_path / "good"
    bad_dir.mkdir()
    good_dir.mkdir()
    bad = bad_dir / "httpx"
    good = good_dir / "httpx"
    _write_executable(bad, "#!/bin/sh\necho 'Python HTTP client CLI --help --version'\n")
    _write_executable(good, "#!/bin/sh\necho 'ProjectDiscovery httpx -u -silent -status-code -tech-detect -timeout'\n")

    resolution = resolve_projectdiscovery_httpx(
        environ={"PATH": f"{bad_dir}{os.pathsep}{good_dir}"}
    )

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
