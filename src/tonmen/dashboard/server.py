from __future__ import annotations

import json
import secrets
import threading
import webbrowser
from dataclasses import asdict
from importlib import resources
from typing import Any
from urllib.parse import unquote, urlparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from tonmen import __version__
from tonmen.agents import MissionPlanner, MissionPlanningDenied, MissionRunDenied
from tonmen.chronicle import ChronicleStore
from tonmen.core.config import DEFAULT_ALLOWED_TARGETS, TonmenConfig
from tonmen.core.runtime import TonmenRuntime
from tonmen.doctor import run_doctor
from tonmen.loop import MissionLoop, MissionLoopPolicy
from tonmen.missions import MissionRunState, StepExecutionState
from tonmen.policy import validate_scope_rule
from tonmen.reasoning import MissionReasoner

_LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}
_STATIC_TYPES = {
    "app.css": "text/css; charset=utf-8",
    "viewport.css": "text/css; charset=utf-8",
    "app.js": "text/javascript; charset=utf-8",
    "deck.js": "text/javascript; charset=utf-8",
}


def validate_console_host(host: str) -> str:
    value = host.strip().lower()
    if value not in _LOOPBACK_HOSTS:
        raise ValueError("TONMEN Console may only bind to a loopback interface")
    return value


def _waiting_step(plan, run):
    for planned, execution in zip(plan.steps, run.steps, strict=True):
        if execution.state is StepExecutionState.WAITING_APPROVAL:
            return planned
    return None


def _iso(value):
    return value.isoformat() if value else None


def _node_payload(node) -> dict[str, Any]:
    return {"id": node.id, "kind": node.kind, "label": node.label, "metadata": dict(node.metadata)}


def mission_payload(plan, run) -> dict[str, Any]:
    planned = {step.id: step for step in plan.steps}
    reasoning_nodes = [_node_payload(node) for node in run.graph.nodes.values() if node.kind.startswith("reasoning.")]
    intelligence_nodes = [_node_payload(node) for node in run.graph.nodes.values() if node.kind.startswith("intelligence.")]
    loop_nodes = [_node_payload(node) for node in run.graph.nodes.values() if node.kind.startswith("loop.")]
    return {
        "id": run.id,
        "plan_id": plan.id,
        "target": run.target,
        "state": run.state.value,
        "started_at": _iso(run.started_at),
        "finished_at": _iso(run.finished_at),
        "steps": [
            {
                "id": execution.step_id,
                "tool": execution.tool,
                "target": execution.target,
                "state": execution.state.value,
                "error": execution.error,
                "job_id": execution.job_id,
                "evidence_id": execution.evidence_id,
                "observation_id": execution.observation_id,
                "metadata": dict(execution.metadata),
                "risk": planned[execution.step_id].risk if execution.step_id in planned else None,
                "requires_approval": planned[execution.step_id].requires_approval if execution.step_id in planned else False,
                "rationale": planned[execution.step_id].rationale if execution.step_id in planned else "",
            }
            for execution in run.steps
        ],
        "observations": [
            {
                "id": item.id,
                "source": item.source,
                "target": item.target,
                "summary": item.summary,
                "evidence_id": item.evidence_id,
                "captured_at": _iso(item.captured_at),
                "metadata": dict(item.metadata),
            }
            for item in run.observations
        ],
        "evidence": [
            {
                "id": item.id,
                "tool": item.tool,
                "target": item.target,
                "argv": list(item.argv),
                "exit_code": item.exit_code,
                "stdout": item.stdout,
                "stderr": item.stderr,
                "started_at": _iso(item.started_at),
                "finished_at": _iso(item.finished_at),
            }
            for item in run.evidence
        ],
        "intelligence": intelligence_nodes,
        "reasoning": reasoning_nodes,
        "loop": loop_nodes,
        "graph": {
            "nodes": [_node_payload(node) for node in run.graph.nodes.values()],
            "edges": [
                {"source": edge.source, "relation": edge.relation, "target": edge.target}
                for edge in run.graph.edges
            ],
        },
    }


class DashboardState:
    """Thread-safe facade over the existing governed TONMEN runtime."""

    def __init__(self, config: TonmenConfig) -> None:
        self._lock = threading.RLock()
        self.config = config
        self.runtime = TonmenRuntime.sentinel(config)
        self.chronicle = ChronicleStore(config.workspace)

    def _reload_runtime(self, config: TonmenConfig) -> None:
        self.config = config
        self.runtime = TonmenRuntime.sentinel(config)
        self.chronicle = ChronicleStore(config.workspace)

    def status(self) -> dict[str, Any]:
        with self._lock:
            report = run_doctor(self.config)
            return {
                "version": __version__,
                "components": [
                    {"id": "core", "zh": "天樞", "en": "Core", "state": "Online", "tone": "green"},
                    {"id": "guard", "zh": "天律", "en": "Guard", "state": "Enforced", "tone": "green"},
                    {"id": "registry", "zh": "天工", "en": "Registry", "state": f"{len(self.runtime.registry)} Tools Ready", "tone": "blue"},
                    {"id": "intel", "zh": "天鑑", "en": "Intelligence", "state": "Active", "tone": "purple"},
                    {"id": "reasoner", "zh": "天策", "en": "Reasoner", "state": "Ready", "tone": "amber"},
                    {"id": "loop", "zh": "天衡", "en": "Mission Loop", "state": "Bounded", "tone": "cyan"},
                ],
                "doctor": {"ready": report.ready, "checks": [asdict(check) for check in report.checks]},
                "workspace": str(self.config.workspace),
                "config_path": str(self.config.config_path) if self.config.config_path else None,
            }

    def scope(self) -> dict[str, Any]:
        with self._lock:
            return {
                "allowed": [
                    {"rule": rule, "default": rule in DEFAULT_ALLOWED_TARGETS}
                    for rule in self.config.allowed_targets
                ],
                "denied": list(self.config.denied_targets),
            }

    def add_scope(self, raw_rule: str) -> dict[str, Any]:
        with self._lock:
            rule = validate_scope_rule(raw_rule)
            updated = self.config.with_allowed_target(rule)
            updated.save()
            self._reload_runtime(updated)
            return self.scope()

    def remove_scope(self, raw_rule: str) -> dict[str, Any]:
        with self._lock:
            rule = validate_scope_rule(raw_rule)
            updated = self.config.without_allowed_target(rule)
            updated.save()
            self._reload_runtime(updated)
            return self.scope()

    def missions(self) -> list[dict[str, Any]]:
        with self._lock:
            return [
                {
                    "id": entry.run_id,
                    "plan_id": entry.plan_id,
                    "target": entry.target,
                    "state": entry.state.value,
                    "started_at": _iso(entry.started_at),
                    "finished_at": _iso(entry.finished_at),
                }
                for entry in self.chronicle.list()
            ]

    def mission(self, run_id: str) -> dict[str, Any]:
        with self._lock:
            plan, run = self.chronicle.load(run_id)
            return mission_payload(plan, run)

    def start_mission(self, target: str, policy: MissionLoopPolicy | None = None) -> dict[str, Any]:
        with self._lock:
            plan = MissionPlanner(self.runtime).plan(target)
            result = MissionLoop(self.runtime, policy or MissionLoopPolicy()).run(plan)
            self.chronicle.save(plan, result.run)
            payload = mission_payload(plan, result.run)
            payload["stop_reason"] = result.stop_reason.value
            return payload

    def resume_mission(self, run_id: str, policy: MissionLoopPolicy | None = None) -> dict[str, Any]:
        with self._lock:
            plan, run = self.chronicle.load(run_id)
            if run.state is not MissionRunState.RUNNING:
                raise ValueError("mission is not budget-stopped in a resumable running state")
            result = MissionLoop(self.runtime, policy or MissionLoopPolicy()).resume(plan, run)
            self.chronicle.save(plan, result.run)
            payload = mission_payload(plan, result.run)
            payload["stop_reason"] = result.stop_reason.value
            return payload

    def approve_mission(self, run_id: str) -> dict[str, Any]:
        with self._lock:
            plan, run = self.chronicle.load(run_id)
            if run.state is not MissionRunState.WAITING_APPROVAL:
                raise ValueError("mission is not waiting for approval")
            waiting = _waiting_step(plan, run)
            if waiting is None:
                raise ValueError("approval-gated step is missing")
            if self.runtime.approvals is None:
                raise ValueError("approval store is unavailable")
            grant = self.runtime.approvals.issue(tool=waiting.tool, target=waiting.target)
            result = MissionLoop(self.runtime).resume(
                plan,
                run,
                approval_tokens={waiting.id: grant.token},
            )
            self.chronicle.save(plan, result.run)
            payload = mission_payload(plan, result.run)
            payload["stop_reason"] = result.stop_reason.value
            return payload

    def reason(self, run_id: str) -> dict[str, Any]:
        with self._lock:
            plan, run = self.chronicle.load(run_id)
            decision = MissionReasoner().decide(plan, run)
            return {
                "id": decision.id,
                "action": decision.action.value,
                "summary": decision.summary,
                "basis_fact_ids": list(decision.basis_fact_ids),
                "next_step_id": decision.next_step_id,
                "requires_human": decision.requires_human,
            }


class TonmenDashboardServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, state: DashboardState):
        self.state = state
        self.csrf_token = secrets.token_urlsafe(32)
        super().__init__(address, TonmenDashboardHandler)


class TonmenDashboardHandler(BaseHTTPRequestHandler):
    server: TonmenDashboardServer

    def log_message(self, fmt: str, *args) -> None:
        if args and str(args[1]).startswith(("4", "5")):
            super().log_message(fmt, *args)

    def _security_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; "
            "base-uri 'none'; form-action 'self'",
        )

    def _send_bytes(self, status: int, content_type: str, payload: bytes, *, cache: str = "no-store") -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", cache)
        self._security_headers()
        self.end_headers()
        self.wfile.write(payload)

    def _json(self, status: int, payload: Any) -> None:
        self._send_bytes(
            status,
            "application/json; charset=utf-8",
            json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        )

    def _error(self, status: int, message: str) -> None:
        self._json(status, {"error": message})

    def _read_json(self) -> dict[str, Any]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise ValueError("invalid content length") from exc
        if length > 65536:
            raise ValueError("request body is too large")
        raw = self.rfile.read(length)
        if not raw:
            return {}
        data = json.loads(raw.decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError("JSON body must be an object")
        return data

    def _csrf_ok(self) -> bool:
        if self.headers.get("X-TONMEN-CSRF") != self.server.csrf_token:
            return False
        origin = self.headers.get("Origin")
        host = self.headers.get("Host", "")
        return not origin or urlparse(origin).netloc == host

    def _asset(self, name: str) -> bytes:
        return resources.files("tonmen.dashboard.static").joinpath(name).read_bytes()

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        try:
            if path == "/":
                html = (
                    self._asset("index.html")
                    .decode("utf-8")
                    .replace("__TONMEN_CSRF__", self.server.csrf_token)
                )
                self._send_bytes(200, "text/html; charset=utf-8", html.encode("utf-8"))
                return
            if path.startswith("/assets/"):
                name = unquote(path.removeprefix("/assets/"))
                content_type = _STATIC_TYPES.get(name)
                if content_type is None:
                    self._error(404, "asset not found")
                    return
                self._send_bytes(
                    200,
                    content_type,
                    self._asset(name),
                    cache="public, max-age=300",
                )
                return
            if path == "/api/status":
                self._json(200, self.server.state.status())
                return
            if path == "/api/scope":
                self._json(200, self.server.state.scope())
                return
            if path == "/api/missions":
                self._json(200, {"missions": self.server.state.missions()})
                return
            if path.startswith("/api/missions/") and path.endswith("/reason"):
                self._json(200, self.server.state.reason(unquote(path.split("/")[3])))
                return
            if path.startswith("/api/missions/"):
                self._json(200, self.server.state.mission(unquote(path.split("/")[3])))
                return
            self._error(404, "not found")
        except FileNotFoundError:
            self._error(404, "mission not found")
        except (ValueError, OSError, json.JSONDecodeError) as exc:
            self._error(400, str(exc))
        except Exception as exc:
            self._error(500, f"dashboard error: {exc}")

    def do_POST(self) -> None:
        if not self._csrf_ok():
            self._error(403, "invalid local CSRF token or origin")
            return
        path = urlparse(self.path).path
        try:
            data = self._read_json()
            if path == "/api/scope/add":
                self._json(200, self.server.state.add_scope(str(data.get("target", ""))))
                return
            if path == "/api/scope/remove":
                self._json(200, self.server.state.remove_scope(str(data.get("target", ""))))
                return
            if path == "/api/missions/start":
                target = str(data.get("target", "")).strip()
                if not target:
                    raise ValueError("target is required")
                policy = MissionLoopPolicy(
                    max_iterations=int(data.get("max_iterations", 8)),
                    max_executions=int(data.get("max_executions", 3)),
                    max_repeat_decisions=int(data.get("max_repeat_decisions", 2)),
                    max_duration_seconds=int(data.get("max_duration_seconds", 300)),
                )
                self._json(200, self.server.state.start_mission(target, policy))
                return
            if path.startswith("/api/missions/") and path.endswith("/approve"):
                self._json(200, self.server.state.approve_mission(unquote(path.split("/")[3])))
                return
            if path.startswith("/api/missions/") and path.endswith("/resume"):
                self._json(200, self.server.state.resume_mission(unquote(path.split("/")[3])))
                return
            self._error(404, "not found")
        except (
            MissionPlanningDenied,
            MissionRunDenied,
            ValueError,
            OSError,
            FileNotFoundError,
            json.JSONDecodeError,
        ) as exc:
            self._error(400, str(exc))
        except Exception as exc:
            self._error(500, f"dashboard error: {exc}")


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
    server = TonmenDashboardServer((host, bind_port), DashboardState(config))
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
