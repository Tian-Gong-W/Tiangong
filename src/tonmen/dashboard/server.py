from __future__ import annotations

import json
import secrets
import threading
import webbrowser
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from tonmen import __version__
from tonmen.agents import MissionPlanner, MissionPlanningDenied, MissionRunDenied
from tonmen.ai import LeadAIOrchestrator
from tonmen.chronicle import ChronicleStore
from tonmen.core.config import DEFAULT_ALLOWED_TARGETS, TonmenConfig
from tonmen.core.runtime import TonmenRuntime
from tonmen.doctor import run_doctor
from tonmen.events import EventBus
from tonmen.loop import MissionLoop, MissionLoopPolicy
from tonmen.missions import MissionRunState, StepExecutionState
from tonmen.policy import validate_scope_rule
from tonmen.reasoning import MissionReasoner
from tonmen.reports import ReportStore
from tonmen.tools.base import RiskLevel

_LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}
_APP_ROUTES = {"/", "/missions", "/scope", "/guard", "/tools", "/intelligence", "/reasoner", "/lead", "/loop", "/chronicle", "/approval", "/settings"}
_TERMINAL_MISSION_STATES = {MissionRunState.SUCCEEDED, MissionRunState.FAILED, MissionRunState.DENIED}
_STATIC_TYPES = {
    "app.css": "text/css; charset=utf-8",
    "viewport.css": "text/css; charset=utf-8",
    "module-pages.css": "text/css; charset=utf-8",
    "events.css": "text/css; charset=utf-8",
    "history-delete.css": "text/css; charset=utf-8",
    "reports.css": "text/css; charset=utf-8",
    "lead-ai.css": "text/css; charset=utf-8",
    "app.js": "text/javascript; charset=utf-8",
    "deck.js": "text/javascript; charset=utf-8",
    "module-pages.js": "text/javascript; charset=utf-8",
    "events.js": "text/javascript; charset=utf-8",
    "history-delete.js": "text/javascript; charset=utf-8",
    "reports.js": "text/javascript; charset=utf-8",
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
            {"id": item.id, "source": item.source, "target": item.target, "summary": item.summary,
             "evidence_id": item.evidence_id, "captured_at": _iso(item.captured_at), "metadata": dict(item.metadata)}
            for item in run.observations
        ],
        "evidence": [
            {"id": item.id, "tool": item.tool, "target": item.target, "argv": list(item.argv),
             "exit_code": item.exit_code, "stdout": item.stdout, "stderr": item.stderr,
             "started_at": _iso(item.started_at), "finished_at": _iso(item.finished_at)}
            for item in run.evidence
        ],
        "intelligence": [_node_payload(node) for node in run.graph.nodes.values() if node.kind.startswith("intelligence.")],
        "reasoning": [_node_payload(node) for node in run.graph.nodes.values() if node.kind.startswith("reasoning.")],
        "loop": [_node_payload(node) for node in run.graph.nodes.values() if node.kind.startswith("loop.")],
        "council": [_node_payload(node) for node in run.graph.nodes.values() if node.kind.startswith("council.")],
        "graph": {
            "nodes": [_node_payload(node) for node in run.graph.nodes.values()],
            "edges": [{"source": edge.source, "relation": edge.relation, "target": edge.target} for edge in run.graph.edges],
        },
    }


class DashboardState:
    """Thread-safe facade over the governed runtime plus a cursor event stream."""

    def __init__(self, config: TonmenConfig) -> None:
        self._lock = threading.RLock()
        self.config = config
        self.events = EventBus()
        self.runtime = TonmenRuntime.sentinel(config, events=self.events)
        self.chronicle = ChronicleStore(config.workspace)
        self.reports = ReportStore(config.workspace)

    def _reload_runtime(self, config: TonmenConfig) -> None:
        self.config = config
        self.runtime = TonmenRuntime.sentinel(config, events=self.events)
        self.chronicle = ChronicleStore(config.workspace)
        self.reports = ReportStore(config.workspace)

    def _checkpoint(self, plan, run) -> None:
        with self._lock:
            self.chronicle.save(plan, run)
            report = self.reports.save(plan, run)
            if report["report_type"] == "final":
                self.events.publish(
                    "report.ready",
                    mission_id=run.id,
                    plan_id=plan.id,
                    target=run.target,
                    state=run.state.value,
                    findings=report["summary"]["findings"],
                    payloads=report["summary"]["executed_payloads"],
                    assessment_rounds=report["summary"]["assessment_rounds"],
                    subagent_reviews=report["summary"]["subagent_reviews"],
                    lead_directives=report["summary"].get("lead_directives", 0),
                    lead_model_calls=report["summary"].get("lead_model_calls", 0),
                )

    def _tool_readiness(self, tool: str):
        return self.runtime.registry.get(tool).readiness()

    def _require_tool_ready(self, tool: str, *, mission_id: str | None = None, step_id: str | None = None) -> None:
        readiness = self._tool_readiness(tool)
        if readiness.ready:
            return
        self.events.publish(
            "tool.preflight_blocked",
            tool=tool,
            mission_id=mission_id,
            step_id=step_id,
            code=readiness.code,
            detail=readiness.detail,
            remediation=readiness.remediation,
        )
        message = f"{tool} preflight blocked: {readiness.detail}"
        if readiness.remediation:
            message += f" Fix: {readiness.remediation}"
        raise ValueError(message)

    @staticmethod
    def _policy_from_run(run, policy: MissionLoopPolicy | None = None) -> MissionLoopPolicy:
        if policy is not None:
            return policy
        sessions = [node for node in run.graph.nodes.values() if node.kind == "loop.session"]
        metadata = sessions[-1].metadata if sessions else {}
        return MissionLoopPolicy(
            assessment_rounds=int(metadata.get("assessment_rounds", 8)),
            subagents_per_round=int(metadata.get("subagents_per_round", 4)),
        )

    def event_stream(self, cursor: int = 0, timeout: float = 20.0, limit: int = 200) -> dict[str, Any]:
        events = self.events.wait_after(cursor, timeout=timeout, limit=limit)
        latest = events[-1].cursor if events else max(int(cursor), self.events.cursor)
        return {"cursor": latest, "events": [event.as_dict() for event in events]}

    def lead_ai(self) -> dict[str, Any]:
        """Return public Lead AI state without ever exposing the configured secret."""
        with self._lock:
            lead = LeadAIOrchestrator()
            config = lead.public_status()
            entries = list(self.chronicle.list())
            ordered = [item for item in entries if item.state in {MissionRunState.RUNNING, MissionRunState.WAITING_APPROVAL}]
            ordered.extend(item for item in entries if item not in ordered)

            selected = None
            for entry in ordered[:40]:
                try:
                    plan, run = self.chronicle.load(entry.run_id)
                except (FileNotFoundError, ValueError, OSError):
                    continue
                directives = [node for node in run.graph.nodes.values() if node.kind == "council.lead"]
                if not directives:
                    continue
                latest = directives[-1]
                latest_md = dict(latest.metadata)
                round_id = next(
                    (
                        node.id
                        for node in run.graph.nodes.values()
                        if node.kind == "council.round" and node.metadata.get("lead_directive_id") == latest.id
                    ),
                    None,
                )
                subagents = [
                    _node_payload(node)
                    for node in run.graph.nodes.values()
                    if node.kind == "council.subagent" and node.metadata.get("lead_directive_id") == latest.id
                ]
                sessions = [node for node in run.graph.nodes.values() if node.kind == "loop.session"]
                policy = dict(sessions[-1].metadata) if sessions else {"assessment_rounds": 8, "subagents_per_round": 4}
                latencies = [
                    int(node.metadata["latency_ms"])
                    for node in directives
                    if isinstance(node.metadata.get("latency_ms"), int)
                ]
                def token_total(name: str) -> int:
                    return sum(
                        int(node.metadata[name])
                        for node in directives
                        if isinstance(node.metadata.get(name), int)
                    )
                selected = {
                    "mission": {
                        "id": run.id,
                        "plan_id": plan.id,
                        "target": run.target,
                        "state": run.state.value,
                    },
                    "latest_directive": _node_payload(latest),
                    "current_round_id": round_id,
                    "subagents": subagents,
                    "rounds_completed": len([node for node in run.graph.nodes.values() if node.kind == "council.round"]),
                    "target_rounds": int(policy.get("assessment_rounds", 8)),
                    "subagents_per_round": int(policy.get("subagents_per_round", 4)),
                    "telemetry": {
                        "directives": len(directives),
                        "model_calls": sum(1 for node in directives if node.metadata.get("source") == "model"),
                        "fallback_calls": sum(1 for node in directives if node.metadata.get("source") != "model"),
                        "input_tokens": token_total("input_tokens"),
                        "output_tokens": token_total("output_tokens"),
                        "total_tokens": token_total("total_tokens"),
                        "latency_ms_total": sum(latencies),
                        "latency_ms_average": round(sum(latencies) / len(latencies)) if latencies else None,
                        "last_latency_ms": latest_md.get("latency_ms"),
                    },
                }
                break

            return {
                "config": config,
                "current": selected,
                "privacy": {
                    "secret_persisted": False,
                    "secret_exposed_to_browser": False,
                    "raw_evidence_sent": False,
                    "approval_tokens_sent": False,
                },
                "authority": {
                    "execution": False,
                    "approval": False,
                    "scope": False,
                    "plan_mutation": False,
                },
            }

    def status(self) -> dict[str, Any]:
        with self._lock:
            report = run_doctor(self.config)
            readiness = [adapter.readiness() for adapter in self.runtime.registry]
            ready_tools = sum(1 for item in readiness if item.ready)
            total_tools = len(readiness)
            return {
                "version": __version__,
                "components": [
                    {"id": "core", "zh": "天樞", "en": "Core", "state": "Online", "tone": "green"},
                    {"id": "guard", "zh": "天律", "en": "Guard", "state": "Enforced", "tone": "green"},
                    {"id": "registry", "zh": "天工", "en": "Registry", "state": f"{ready_tools}/{total_tools} Tools Ready", "tone": "blue" if ready_tools == total_tools else "amber"},
                    {"id": "intel", "zh": "天鑑", "en": "Intelligence", "state": "Active", "tone": "purple"},
                    {"id": "reasoner", "zh": "天策", "en": "Reasoner", "state": "Ready", "tone": "amber"},
                    {"id": "loop", "zh": "天衡", "en": "Mission Loop", "state": "Event-driven", "tone": "cyan"},
                ],
                "doctor": {"ready": report.ready, "checks": [asdict(check) for check in report.checks]},
                "workspace": str(self.config.workspace),
                "config_path": str(self.config.config_path) if self.config.config_path else None,
                "event_cursor": self.events.cursor,
                "lead_ai": self.lead_ai()["config"],
            }

    def scope(self) -> dict[str, Any]:
        with self._lock:
            return {"allowed": [{"rule": rule, "default": rule in DEFAULT_ALLOWED_TARGETS} for rule in self.config.allowed_targets],
                    "denied": list(self.config.denied_targets)}

    def add_scope(self, raw_rule: str) -> dict[str, Any]:
        with self._lock:
            rule = validate_scope_rule(raw_rule)
            updated = self.config.with_allowed_target(rule)
            updated.save(); self._reload_runtime(updated)
            self.events.publish("scope.updated", action="add", rule=rule)
            return self.scope()

    def remove_scope(self, raw_rule: str) -> dict[str, Any]:
        with self._lock:
            rule = validate_scope_rule(raw_rule)
            updated = self.config.without_allowed_target(rule)
            updated.save(); self._reload_runtime(updated)
            self.events.publish("scope.updated", action="remove", rule=rule)
            return self.scope()

    def missions(self) -> list[dict[str, Any]]:
        with self._lock:
            return [{"id": entry.run_id, "plan_id": entry.plan_id, "target": entry.target,
                     "state": entry.state.value, "started_at": _iso(entry.started_at), "finished_at": _iso(entry.finished_at)}
                    for entry in self.chronicle.list()]

    def mission(self, run_id: str) -> dict[str, Any]:
        with self._lock:
            plan, run = self.chronicle.load(run_id)
            return mission_payload(plan, run)

    def report(self, run_id: str, *, markdown: bool = False):
        with self._lock:
            try:
                return self.reports.load_markdown(run_id) if markdown else self.reports.load_json(run_id)
            except FileNotFoundError:
                plan, run = self.chronicle.load(run_id)
                self.reports.save(plan, run)
                return self.reports.load_markdown(run_id) if markdown else self.reports.load_json(run_id)

    def delete_mission(self, run_id: str) -> dict[str, Any]:
        with self._lock:
            _, run = self.chronicle.load(run_id)
            if run.state not in _TERMINAL_MISSION_STATES:
                raise ValueError("only completed, failed or denied missions may be deleted")
            if not self.chronicle.delete(run.id):
                raise FileNotFoundError(run.id)
            self.reports.delete(run.id)
            if self.runtime.audit is not None:
                self.runtime.audit.append(
                    action="mission.delete",
                    tool="chronicle",
                    target=run.target,
                    decision="delete",
                    message=f"deleted terminal mission {run.id} ({run.state.value})",
                )
            self.events.publish(
                "mission.deleted",
                mission_id=run.id,
                target=run.target,
                state=run.state.value,
            )
            return {"deleted": run.id, "remaining": len(self.chronicle.list())}

    def cleanup_terminal_missions(self) -> dict[str, Any]:
        with self._lock:
            deleted: list[str] = []
            for entry in self.chronicle.list():
                if entry.state not in _TERMINAL_MISSION_STATES:
                    continue
                if self.chronicle.delete(entry.run_id):
                    self.reports.delete(entry.run_id)
                    deleted.append(entry.run_id)
                    if self.runtime.audit is not None:
                        self.runtime.audit.append(
                            action="mission.delete",
                            tool="chronicle",
                            target=entry.target,
                            decision="delete",
                            message=f"deleted terminal mission {entry.run_id} ({entry.state.value}) during cleanup",
                        )
            self.events.publish("missions.cleaned", deleted=len(deleted))
            return {"deleted": deleted, "count": len(deleted), "remaining": len(self.chronicle.list())}

    def tools(self) -> dict[str, Any]:
        with self._lock:
            checks = {check.name: asdict(check) for check in run_doctor(self.config).checks}
            tools = []
            for adapter in self.runtime.registry:
                spec = adapter.spec
                check = checks.get(spec.name)
                readiness = adapter.readiness()
                tools.append({
                    "name": spec.name,
                    "category": spec.category,
                    "description": spec.description,
                    "risk": int(spec.risk),
                    "risk_name": spec.risk.name.lower(),
                    "capabilities": list(spec.capabilities),
                    "available": readiness.ready,
                    "readiness": asdict(readiness),
                    "doctor": check,
                })
            return {"count": len(tools), "ready": sum(1 for tool in tools if tool["available"]), "tools": tools}

    def audit(self, limit: int = 200) -> dict[str, Any]:
        with self._lock:
            bounded = max(1, min(int(limit), 500)); path = self.config.workspace / "audit.jsonl"
            if not path.exists(): return {"path": str(path), "events": []}
            events = []
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines()[-bounded:]:
                try: item = json.loads(line)
                except json.JSONDecodeError: continue
                if isinstance(item, dict): events.append(item)
            return {"path": str(path), "events": events}

    def guard(self) -> dict[str, Any]:
        with self._lock:
            waiting = sum(1 for item in self.chronicle.list() if item.state is MissionRunState.WAITING_APPROVAL)
            return {
                "mode": "deny-by-default", "scope": self.scope(), "pending_approvals": waiting,
                "risk_levels": [{"level": int(level), "name": level.name.lower()} for level in RiskLevel],
                "rules": [
                    {"name": "scope", "decision": "deny", "detail": "Targets outside authorized Scope are denied."},
                    {"name": "low-risk", "decision": "allow", "detail": "Passive/discovery work may run autonomously inside Scope."},
                    {"name": "validation", "decision": "approval", "detail": "Validation/intrusive actions require a bound single-use grant."},
                    {"name": "destructive", "decision": "deny", "detail": "Destructive actions remain disabled."},
                ], "audit": self.audit(100),
            }

    def settings(self) -> dict[str, Any]:
        with self._lock:
            return {"version": __version__, "workspace": str(self.config.workspace),
                    "config_path": str(self.config.config_path) if self.config.config_path else None,
                    "bind_host": self.config.bind_host, "bind_port": self.config.bind_port,
                    "command_timeout_seconds": self.config.command_timeout_seconds,
                    "allowed_targets": list(self.config.allowed_targets), "denied_targets": list(self.config.denied_targets),
                    "allow_arbitrary_shell": self.config.allow_arbitrary_shell, "console_loopback_only": True,
                    "default_assessment_rounds": 8, "default_subagents_per_round": 4,
                    "event_cursor": self.events.cursor}

    def start_mission(self, target: str, policy: MissionLoopPolicy | None = None) -> dict[str, Any]:
        plan = MissionPlanner(self.runtime).plan(target)
        for step in plan.steps:
            if not step.requires_approval:
                self._require_tool_ready(step.tool, step_id=step.id)
        result = MissionLoop(self.runtime, policy or MissionLoopPolicy(), checkpoint=self._checkpoint).run(plan)
        self._checkpoint(plan, result.run)
        payload = mission_payload(plan, result.run); payload["stop_reason"] = result.stop_reason.value
        return payload

    def resume_mission(self, run_id: str, policy: MissionLoopPolicy | None = None) -> dict[str, Any]:
        with self._lock:
            plan, run = self.chronicle.load(run_id)
        if run.state is not MissionRunState.RUNNING:
            raise ValueError("mission is not budget-stopped in a resumable running state")
        resolved_policy = self._policy_from_run(run, policy)
        result = MissionLoop(self.runtime, resolved_policy, checkpoint=self._checkpoint).resume(plan, run)
        self._checkpoint(plan, result.run)
        payload = mission_payload(plan, result.run); payload["stop_reason"] = result.stop_reason.value
        return payload

    def approve_mission(self, run_id: str) -> dict[str, Any]:
        with self._lock:
            plan, run = self.chronicle.load(run_id)
        if run.state is not MissionRunState.WAITING_APPROVAL: raise ValueError("mission is not waiting for approval")
        waiting = _waiting_step(plan, run)
        if waiting is None: raise ValueError("approval-gated step is missing")
        self._require_tool_ready(waiting.tool, mission_id=run.id, step_id=waiting.id)
        if self.runtime.approvals is None: raise ValueError("approval store is unavailable")
        grant = self.runtime.approvals.issue(tool=waiting.tool, target=waiting.target)
        self.events.publish("approval.granted", mission_id=run.id, plan_id=plan.id, target=run.target,
                            step_id=waiting.id, tool=waiting.tool, step_target=waiting.target)
        result = MissionLoop(self.runtime, self._policy_from_run(run), checkpoint=self._checkpoint).resume(
            plan, run, approval_tokens={waiting.id: grant.token})
        self._checkpoint(plan, result.run)
        payload = mission_payload(plan, result.run); payload["stop_reason"] = result.stop_reason.value
        return payload

    def reason(self, run_id: str) -> dict[str, Any]:
        with self._lock:
            plan, run = self.chronicle.load(run_id)
        decision = MissionReasoner().decide(plan, run)
        return {"id": decision.id, "action": decision.action.value, "summary": decision.summary,
                "basis_fact_ids": list(decision.basis_fact_ids), "next_step_id": decision.next_step_id,
                "requires_human": decision.requires_human}


class TonmenDashboardServer(ThreadingHTTPServer):
    daemon_threads = True
    def __init__(self, address, state: DashboardState):
        self.state = state; self.csrf_token = secrets.token_urlsafe(32)
        super().__init__(address, TonmenDashboardHandler)


class TonmenDashboardHandler(BaseHTTPRequestHandler):
    server: TonmenDashboardServer
    def log_message(self, fmt: str, *args) -> None:
        if args and str(args[1]).startswith(("4", "5")): super().log_message(fmt, *args)

    def _security_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff"); self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")

    def _send_bytes(self, status: int, content_type: str, payload: bytes, *, cache: str = "no-store") -> None:
        self.send_response(status); self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload))); self.send_header("Cache-Control", cache)
        self._security_headers(); self.end_headers(); self.wfile.write(payload)

    def _json(self, status: int, payload: Any) -> None:
        self._send_bytes(status, "application/json; charset=utf-8", json.dumps(payload, ensure_ascii=False).encode("utf-8"))
    def _error(self, status: int, message: str) -> None: self._json(status, {"error": message})

    def _read_json(self) -> dict[str, Any]:
        try: length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc: raise ValueError("invalid content length") from exc
        if length > 65536: raise ValueError("request body is too large")
        raw = self.rfile.read(length)
        if not raw: return {}
        data = json.loads(raw.decode("utf-8"))
        if not isinstance(data, dict): raise ValueError("JSON body must be an object")
        return data

    def _csrf_ok(self) -> bool:
        if self.headers.get("X-TONMEN-CSRF") != self.server.csrf_token: return False
        origin, host = self.headers.get("Origin"), self.headers.get("Host", "")
        return not origin or urlparse(origin).netloc == host

    def _asset(self, name: str) -> bytes: return resources.files("tonmen.dashboard.static").joinpath(name).read_bytes()
    def _index(self) -> bytes: return self._asset("index.html").decode("utf-8").replace("__TONMEN_CSRF__", self.server.csrf_token).encode("utf-8")

    def do_GET(self) -> None:
        parsed = urlparse(self.path); path = parsed.path.rstrip("/") or "/"
        try:
            if path in _APP_ROUTES: self._send_bytes(200, "text/html; charset=utf-8", self._index()); return
            if path.startswith("/assets/"):
                name = unquote(path.removeprefix("/assets/")); content_type = _STATIC_TYPES.get(name)
                if content_type is None: self._error(404, "asset not found"); return
                payload = self._asset(name)
                if name == "app.js": payload += b"\n" + self._asset("deck.js") + b"\n" + self._asset("module-pages.js") + b"\n" + self._asset("events.js") + b"\n" + self._asset("history-delete.js") + b"\n" + self._asset("reports.js")
                if name == "viewport.css": payload += b"\n" + self._asset("module-pages.css") + b"\n" + self._asset("events.css") + b"\n" + self._asset("history-delete.css") + b"\n" + self._asset("reports.css") + b"\n" + self._asset("lead-ai.css")
                self._send_bytes(200, content_type, payload, cache="no-store"); return
            if path == "/api/events":
                query = parse_qs(parsed.query)
                cursor = int(query.get("cursor", ["0"])[0]); timeout = float(query.get("timeout", ["20"])[0]); limit = int(query.get("limit", ["200"])[0])
                self._json(200, self.server.state.event_stream(cursor, timeout, limit)); return
            if path == "/api/status": self._json(200, self.server.state.status()); return
            if path == "/api/ai/lead": self._json(200, self.server.state.lead_ai()); return
            if path == "/api/scope": self._json(200, self.server.state.scope()); return
            if path == "/api/tools": self._json(200, self.server.state.tools()); return
            if path == "/api/guard": self._json(200, self.server.state.guard()); return
            if path == "/api/audit":
                query = parse_qs(parsed.query); limit = int(query.get("limit", ["200"])[0])
                self._json(200, self.server.state.audit(limit)); return
            if path == "/api/settings": self._json(200, self.server.state.settings()); return
            if path == "/api/missions": self._json(200, {"missions": self.server.state.missions()}); return
            if path.startswith("/api/missions/") and path.endswith("/reason"):
                self._json(200, self.server.state.reason(unquote(path.split("/")[3]))); return
            if path.startswith("/api/missions/") and path.endswith("/report"):
                run_id = unquote(path.split("/")[3])
                query = parse_qs(parsed.query)
                markdown = query.get("format", ["json"])[0].lower() in {"md", "markdown"}
                if markdown:
                    payload = self.server.state.report(run_id, markdown=True).encode("utf-8")
                    self._send_bytes(200, "text/markdown; charset=utf-8", payload); return
                self._json(200, self.server.state.report(run_id)); return
            if path.startswith("/api/missions/"):
                self._json(200, self.server.state.mission(unquote(path.split("/")[3]))); return
            self._error(404, "not found")
        except FileNotFoundError: self._error(404, "mission not found")
        except (ValueError, OSError, json.JSONDecodeError) as exc: self._error(400, str(exc))
        except Exception as exc: self._error(500, f"dashboard error: {exc}")

    def do_POST(self) -> None:
        if not self._csrf_ok(): self._error(403, "invalid local CSRF token or origin"); return
        path = urlparse(self.path).path
        try:
            data = self._read_json()
            if path == "/api/scope/add": self._json(200, self.server.state.add_scope(str(data.get("target", "")))); return
            if path == "/api/scope/remove": self._json(200, self.server.state.remove_scope(str(data.get("target", "")))); return
            if path == "/api/missions/start":
                target = str(data.get("target", "")).strip()
                if not target: raise ValueError("target is required")
                policy = MissionLoopPolicy(
                    max_iterations=int(data.get("max_iterations", 8)),
                    max_executions=int(data.get("max_executions", 3)),
                    max_repeat_decisions=int(data.get("max_repeat_decisions", 2)),
                    max_duration_seconds=int(data.get("max_duration_seconds", 300)),
                    assessment_rounds=int(data.get("assessment_rounds", 8)),
                    subagents_per_round=int(data.get("subagents_per_round", 4)),
                )
                self._json(200, self.server.state.start_mission(target, policy)); return
            if path == "/api/missions/cleanup":
                self._json(200, self.server.state.cleanup_terminal_missions()); return
            if path.startswith("/api/missions/") and path.endswith("/delete"):
                self._json(200, self.server.state.delete_mission(unquote(path.split("/")[3]))); return
            if path.startswith("/api/missions/") and path.endswith("/approve"):
                self._json(200, self.server.state.approve_mission(unquote(path.split("/")[3]))); return
            if path.startswith("/api/missions/") and path.endswith("/resume"):
                self._json(200, self.server.state.resume_mission(unquote(path.split("/")[3]))); return
            self._error(404, "not found")
        except (MissionPlanningDenied, MissionRunDenied, ValueError, OSError, FileNotFoundError, json.JSONDecodeError) as exc: self._error(400, str(exc))
        except Exception as exc: self._error(500, f"dashboard error: {exc}")


def serve_dashboard(config: TonmenConfig, *, host: str = "127.0.0.1", port: int | None = None, open_browser: bool = True) -> int:
    host = validate_console_host(host); bind_port = int(port if port is not None else config.bind_port)
    if not 1 <= bind_port <= 65535: raise ValueError("console port must be within 1-65535")
    server = TonmenDashboardServer((host, bind_port), DashboardState(config))
    display_host = "127.0.0.1" if host in {"127.0.0.1", "localhost"} else "[::1]"
    url = f"http://{display_host}:{server.server_address[1]}/"
    print(f"雲頂天宮 Console: {url}"); print("本地控制面板僅綁定 loopback；Ctrl+C 停止。")
    if open_browser: threading.Timer(0.2, lambda: webbrowser.open(url)).start()
    try: server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt: print("\n天宮已閉。")
    finally: server.server_close()
    return 0
