from __future__ import annotations

import secrets
import threading
import webbrowser
from http.server import ThreadingHTTPServer
from importlib import resources
from urllib.parse import unquote, urlparse

from tonmen.core.config import TonmenConfig

from .mission_workspace import build_mission_workspace
from .server import validate_console_host
from .simple_view_server import DashboardState as SimpleViewDashboardState
from .simple_view_server import SimpleViewDashboardHandler

_WORKSPACE_ASSETS = {
    "mission-workspace.css": "text/css; charset=utf-8",
    "mission-workspace.js": "text/javascript; charset=utf-8",
}
_BASE_SCRIPTS = (
    "app.js",
    "deck.js",
    "module-pages.js",
    "events.js",
    "history-delete.js",
    "reports.js",
)


class DashboardState(SimpleViewDashboardState):
    """Adds a read-only exploration/asset projection to Mission detail payloads."""

    def mission(self, run_id: str):
        with self._lock:
            plan, run = self.chronicle.load(run_id)
            payload = super().mission(run_id)
            payload["workspace"] = build_mission_workspace(plan, run)
            return payload


class MissionWorkspaceDashboardHandler(SimpleViewDashboardHandler):
    def _index(self) -> bytes:
        text = super()._index().decode("utf-8")

        # The base server historically concatenated six independent JavaScript
        # modules into /assets/app.js. One syntax error then prevented the browser
        # from parsing the entire bundle and made every Console control appear dead.
        # The production Console now loads those modules independently so a defect
        # remains failure-contained to its own module.
        legacy_app = '<script src="/assets/app.js?v=lean-nav-1"></script>'
        if legacy_app in text:
            scripts = "\n".join(
                f'  <script src="/assets/{name}?v=console-p0-1"></script>'
                for name in _BASE_SCRIPTS
            )
            text = text.replace(legacy_app, scripts)

        if "/assets/mission-workspace.css" not in text:
            text = text.replace(
                "</head>",
                '  <link rel="stylesheet" href="/assets/mission-workspace.css?v=workspace-1">\n</head>',
            )
        if "/assets/mission-workspace.js" not in text:
            text = text.replace(
                "</body>",
                '  <script src="/assets/mission-workspace.js?v=workspace-1"></script>\n</body>',
            )
        return text.encode("utf-8")

    def do_GET(self) -> None:
        path = urlparse(self.path).path.rstrip("/") or "/"
        if path.startswith("/assets/"):
            name = unquote(path.removeprefix("/assets/"))

            # Intercept app.js before the legacy base handler can append the other
            # modules. The remaining base scripts are served individually by the
            # inherited static asset handler.
            if name == "app.js":
                payload = resources.files("tonmen.dashboard.static").joinpath(name).read_bytes()
                self._send_bytes(200, "text/javascript; charset=utf-8", payload, cache="no-store")
                return

            content_type = _WORKSPACE_ASSETS.get(name)
            if content_type is not None:
                payload = resources.files("tonmen.dashboard.static").joinpath(name).read_bytes()
                self._send_bytes(200, content_type, payload, cache="no-store")
                return
        super().do_GET()


class MissionWorkspaceDashboardServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, state: DashboardState):
        self.state = state
        self.csrf_token = secrets.token_urlsafe(32)
        super().__init__(address, MissionWorkspaceDashboardHandler)


def serve_dashboard(
    config: TonmenConfig,
    *,
    host: str = "127.0.0.1",
    port: int | None = None,
    open_browser: bool = True,
) -> int:
    host = validate_console_host(host)
    bind_port = int(port if port is not None else config.bind_port)
    if not 1 <= bind_port <= 65535:
        raise ValueError("console port must be within 1-65535")
    server = MissionWorkspaceDashboardServer((host, bind_port), DashboardState(config))
    display_host = "127.0.0.1" if host in {"127.0.0.1", "localhost"} else "[::1]"
    url = f"http://{display_host}:{server.server_address[1]}/"
    print(f"雲頂天宮 Console: {url}")
    print("本地控制面板僅綁定 loopback；Ctrl+C 停止。")
    if open_browser:
        threading.Timer(0.2, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        print("\n天宮已閉。")
    finally:
        server.server_close()
    return 0
