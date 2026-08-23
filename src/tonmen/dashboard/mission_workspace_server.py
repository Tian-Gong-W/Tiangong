from __future__ import annotations

import secrets
import threading
import webbrowser
from http.server import ThreadingHTTPServer
from importlib import resources
from urllib.parse import unquote, urlparse

from tonmen.core.config import TonmenConfig
from tonmen.missions import MissionRunState, StepExecutionState

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
    """Adds Mission workspace projection and action-aware approval handling."""

    def mission(self, run_id: str):
        with self._lock:
            plan, run = self.chronicle.load(run_id)
            payload = super().mission(run_id)
            for step in payload.get("steps", []):
                metadata = step.get("metadata") or {}
                if not metadata.get("dynamic"):
                    continue
                step["risk"] = metadata.get("risk")
                step["requires_approval"] = bool(metadata.get("requires_approval"))
                step["rationale"] = str(metadata.get("rationale") or "")
            payload["workspace"] = build_mission_workspace(plan, run)
            return payload

    @staticmethod
    def _waiting_execution(run):
        return next(
            (execution for execution in run.steps if execution.state is StepExecutionState.WAITING_APPROVAL),
            None,
        )

    def approve_mission(self, run_id: str) -> dict:
        """Approve either a frozen compatibility action or a dynamic ActionProposal."""
        with self._lock:
            existing = self._approval_jobs.get(run_id)
            if existing and existing.get("status") in {"accepted", "running"}:
                return {**existing, "duplicate_suppressed": True}

            plan, run = self.chronicle.load(run_id)
            if run.state is not MissionRunState.WAITING_APPROVAL:
                raise ValueError("mission is not waiting for approval")
            waiting = self._waiting_execution(run)
            if waiting is None:
                raise ValueError("approval-gated action is missing")

            self._require_tool_ready(waiting.tool, mission_id=run.id, step_id=waiting.id)
            if self.runtime.approvals is None:
                raise ValueError("approval store is unavailable")
            grant = self.runtime.approvals.issue(tool=waiting.tool, target=waiting.target)

            accepted = {
                "run_id": run_id,
                "status": "accepted",
                "state": run.state.value,
                "tool": waiting.tool,
                "action_id": waiting.id,
                "dynamic": bool(waiting.metadata.get("dynamic")),
                "message": "已受理。批准后的动作正在后台执行，你可以继续查看页面，状态会自动更新。",
                "approval_token_exposed": False,
            }
            self._approval_jobs[run_id] = accepted
            self.events.publish(
                "approval.granted",
                mission_id=run.id,
                plan_id=plan.id,
                target=run.target,
                step_id=waiting.id,
                tool=waiting.tool,
                step_target=waiting.target,
                dynamic=bool(waiting.metadata.get("dynamic")),
            )
            thread = threading.Thread(
                target=self._run_approved_mission,
                args=(run_id, plan, run, waiting, grant.token),
                name=f"tonmen-approve-{run_id[:8]}",
                daemon=True,
            )
            thread.start()
            self._approval_jobs[run_id] = {**accepted, "status": "running"}
            return dict(self._approval_jobs[run_id])


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
