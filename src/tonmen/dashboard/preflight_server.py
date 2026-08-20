from __future__ import annotations

import json
import secrets
import threading
import webbrowser
from http.server import ThreadingHTTPServer
from importlib import resources
from typing import Any
from urllib.parse import unquote, urlparse

from tonmen.core.config import TonmenConfig
from tonmen.loop import MissionLoopPolicy
from tonmen.preflight import build_mission_preflight
from tonmen.workers import RemoteWorkerExecutor

from .provider_server import DashboardState as ProviderDashboardState
from .provider_server import ProviderDashboardHandler
from .server import validate_console_host

_PREFLIGHT_ASSETS = {
    "mission-preflight.css": "text/css; charset=utf-8",
    "mission-preflight.js": "text/javascript; charset=utf-8",
}


def _mission_policy(data: dict[str, Any]) -> MissionLoopPolicy:
    defaults = MissionLoopPolicy()
    return MissionLoopPolicy(
        max_iterations=int(data.get("max_iterations", defaults.max_iterations)),
        max_executions=int(data.get("max_executions", defaults.max_executions)),
        max_repeat_decisions=int(data.get("max_repeat_decisions", defaults.max_repeat_decisions)),
        max_duration_seconds=int(data.get("max_duration_seconds", defaults.max_duration_seconds)),
        assessment_rounds=int(data.get("assessment_rounds", defaults.assessment_rounds)),
        subagents_per_round=int(data.get("subagents_per_round", defaults.subagents_per_round)),
    )


class DashboardState(ProviderDashboardState):
    """Operator facade with a side-effect-light Mission preflight surface."""

    def _require_tool_ready(
        self,
        tool: str,
        *,
        mission_id: str | None = None,
        step_id: str | None = None,
    ) -> None:
        # In Worker mode the control plane intentionally does not need local scanner
        # binaries. The RemoteWorkerExecutor performs health/tool-readiness checks on
        # an eligible Worker immediately before dispatch.
        if isinstance(self.runtime.executor, RemoteWorkerExecutor):
            return
        super()._require_tool_ready(tool, mission_id=mission_id, step_id=step_id)

    def mission_preflight(self, target: str, policy: MissionLoopPolicy) -> dict[str, Any]:
        with self._lock:
            payload = build_mission_preflight(self.runtime, target, policy)
            self.events.publish(
                "mission.preflight",
                target=target,
                ready_to_start=payload["ready_to_start"],
                blockers=len(payload["blockers"]),
                warnings=len(payload["warnings"]),
                execution_mode=payload["execution_plane"]["mode"],
            )
            return payload


class MissionPreflightDashboardHandler(ProviderDashboardHandler):
    """Adds Mission preview/readiness without changing execution authority."""

    def _index(self) -> bytes:
        text = super()._index().decode("utf-8")
        if "/assets/mission-preflight.css" not in text:
            text = text.replace(
                "</head>",
                '  <link rel="stylesheet" href="/assets/mission-preflight.css?v=preflight-1">\n</head>',
            )
        if "/assets/mission-preflight.js" not in text:
            text = text.replace(
                "</body>",
                '  <script src="/assets/mission-preflight.js?v=preflight-1"></script>\n</body>',
            )
        return text.encode("utf-8")

    def do_GET(self) -> None:
        path = urlparse(self.path).path.rstrip("/") or "/"
        if path.startswith("/assets/"):
            name = unquote(path.removeprefix("/assets/"))
            content_type = _PREFLIGHT_ASSETS.get(name)
            if content_type is not None:
                payload = resources.files("tonmen.dashboard.static").joinpath(name).read_bytes()
                self._send_bytes(200, content_type, payload, cache="no-store")
                return
        super().do_GET()

    def do_POST(self) -> None:
        path = urlparse(self.path).path.rstrip("/")
        if path not in {"/api/missions/preflight", "/api/missions/start"}:
            super().do_POST()
            return
        if not self._csrf_ok():
            self._error(403, "invalid local CSRF token or origin")
            return
        try:
            data = self._read_json()
            target = str(data.get("target", "")).strip()
            if not target:
                raise ValueError("target is required")
            policy = _mission_policy(data)
            if path == "/api/missions/preflight":
                self._json(200, self.server.state.mission_preflight(target, policy))
                return
            self._json(200, self.server.state.start_mission(target, policy))
        except (ValueError, OSError, FileNotFoundError, json.JSONDecodeError) as exc:
            self._error(400, str(exc))
        except Exception as exc:
            self._error(500, f"mission control error: {exc}")


class MissionPreflightDashboardServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, state: DashboardState):
        self.state = state
        self.csrf_token = secrets.token_urlsafe(32)
        super().__init__(address, MissionPreflightDashboardHandler)


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
    server = MissionPreflightDashboardServer((host, bind_port), DashboardState(config))
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
