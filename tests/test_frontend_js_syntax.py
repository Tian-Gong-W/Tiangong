from __future__ import annotations

import shutil
import subprocess
from importlib import resources

import pytest


def test_all_packaged_console_javascript_parses_with_node():
    """Catch quote/template/bracket syntax errors in every shipped Console module."""
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not available")

    static = resources.files("tonmen.dashboard.static")
    failures: list[str] = []
    checked = 0

    for asset in sorted(static.iterdir(), key=lambda item: item.name):
        if not asset.name.endswith(".js"):
            continue
        checked += 1
        result = subprocess.run(
            [node, "--check", "-"],
            input=asset.read_text(encoding="utf-8"),
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            failures.append(f"{asset.name}:\n{result.stderr.strip()}")

    assert checked > 0
    assert not failures, "JavaScript syntax errors:\n\n" + "\n\n".join(failures)
