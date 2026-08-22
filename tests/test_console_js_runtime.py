from __future__ import annotations

import shutil
import subprocess
import threading
from importlib import resources
from urllib.request import urlopen

import pytest

from tonmen.core.config import TonmenConfig
from tonmen.dashboard.mission_workspace_server import DashboardState, MissionWorkspaceDashboardServer


def test_app_javascript_parses_when_node_is_available():
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")

    source = resources.files("tonmen.dashboard.static").joinpath("app.js").read_text(encoding="utf-8")
    result = subprocess.run(
        [node, "--check", "-"],
        input=source,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_production_console_loads_base_javascript_as_isolated_modules(tmp_path):
    config = TonmenConfig(workspace=tmp_path, allowed_targets=("localhost",))
    server = MissionWorkspaceDashboardServer(("127.0.0.1", 0), DashboardState(config))
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
    thread.start()

    try:
        base = f"http://127.0.0.1:{server.server_address[1]}"
        with urlopen(f"{base}/", timeout=3) as response:
            html = response.read().decode("utf-8")

        expected = (
            "app.js",
            "deck.js",
            "module-pages.js",
            "events.js",
            "history-delete.js",
            "reports.js",
        )
        for name in expected:
            assert f'/assets/{name}?v=console-p0-1' in html

        with urlopen(f"{base}/assets/app.js?v=console-p0-1", timeout=3) as response:
            app_source = response.read().decode("utf-8")

        assert "const state = { missions:" in app_source
        assert "Hard navigation intentionally runs in capture phase" not in app_source
        assert "const liveBuffers = new Map();" not in app_source
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
