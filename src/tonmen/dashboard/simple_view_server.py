from __future__ import annotations

import secrets
import threading
import webbrowser
from http.server import ThreadingHTTPServer
from importlib import resources
from urllib.parse import unquote, urlparse

from tonmen.core.config import TonmenConfig

from .server import validate_console_host
from .usability_server import DashboardState
from .usability_server import UsabilityDashboardHandler

_SIMPLE_ASSETS = {
    "module-simple-view.css": "text/css; charset=utf-8",
    "module-simple-view.js": "text/javascript; charset=utf-8",
}


class SimpleViewDashboardHandler(UsabilityDashboardHandler):
    """Keeps operator pages concise while preserving technical details on demand."""

    def _index(self) -> bytes:
        text = super()._index().decode("utf-8")
        if "/assets/module-simple-view.css" not in text:
            text = text.replace(
                "</head>",
                '  <link rel="stylesheet" href="/assets/module-simple-view.css?v=simple-1">\n</head>',
            )
        if "/assets/module-simple-view.js" not in text:
            text = text.replace(
                "</body>",
                '  <script src="/assets/module-simple-view.js?v=simple-1"></script>\n</body>',
            )
        return text.encode("utf-8")

    def do_GET(self) -> None:
        path = urlparse(self.path).path.rstrip("/") or "/"
        if path.startswith("/assets/"):
            name = unquote(path.removeprefix("/assets/"))
            content_type = _SIMPLE_ASSETS.get(name)
            if content_type is not None:
                payload = resources.files("tonmen.dashboard.static").joinpath(name).read_bytes()
                self._send_bytes(200, content_type, payload, cache="no-store")
                return
        super().do_GET()


class SimpleViewDashboardServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, state: DashboardState):
        self.state = state
        self.csrf_token = secrets.token_urlsafe(32)
        super().__init__(address, SimpleViewDashboardHandler)


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
    server = SimpleViewDashboardServer((host, bind_port), DashboardState(config))
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
