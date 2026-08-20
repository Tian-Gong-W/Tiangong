from __future__ import annotations

import json
import threading
import time
from collections import OrderedDict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Mapping
from urllib.parse import urlparse

from tonmen import __version__
from tonmen.audit import AuditLog
from tonmen.core.config import TonmenConfig
from tonmen.execution import ExecutionDenied, ToolExecutor
from tonmen.policy import ApprovalStore, Decision, PolicyEngine, TargetScope
from tonmen.tools import ToolRegistry, ToolRequest
from tonmen.tools.adapters import register_builtin_adapters

from .protocol import DispatchEnvelope, normalize_worker_id, require_worker_secret

_LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}


class WorkerBusy(RuntimeError):
    pass


def validate_worker_bind_host(host: str, *, allow_remote: bool = False) -> str:
    value = str(host).strip().lower()
    if value in _LOOPBACK_HOSTS:
        return value
    if not allow_remote:
        raise ValueError("remote worker bind requires --allow-remote-bind and a private/firewalled network")
    if value in {"", "0.0.0.0", "::"}:
        raise ValueError("worker may not bind to an unspecified all-interface address")
    return value


class WorkerService:
    """Execution plane accepting only short-lived signed typed tool requests.

    The Worker independently rechecks Scope/Policy and rebuilds argv locally. Its
    own concurrency ceiling is a hard backstop even when multiple control planes
    or stale health information race for execution capacity.
    """

    def __init__(
        self,
        config: TonmenConfig,
        *,
        worker_id: str,
        secret: str,
        region: str = "default",
        tags: tuple[str, ...] = (),
        max_concurrency: int = 4,
    ) -> None:
        if config.allow_arbitrary_shell:
            raise ValueError("TONMEN forbids arbitrary shell execution")
        concurrency = int(max_concurrency)
        if concurrency < 1 or concurrency > 64:
            raise ValueError("worker max_concurrency must be within 1-64")
        self.config = config
        self.worker_id = normalize_worker_id(worker_id)
        self.secret = require_worker_secret(secret)
        self.region = str(region or "default").strip().lower() or "default"
        self.tags = tuple(dict.fromkeys(str(item).strip().lower() for item in tags if str(item).strip()))
        self.max_concurrency = concurrency
        self.registry = ToolRegistry()
        register_builtin_adapters(self.registry)
        self.scope = TargetScope(config.allowed_targets, config.denied_targets)
        self.policy = PolicyEngine(self.scope)
        self.approvals = ApprovalStore()
        config.workspace.mkdir(parents=True, exist_ok=True)
        self.audit = AuditLog(config.workspace / f"worker-{self.worker_id}-audit.jsonl")
        self.executor = ToolExecutor(
            self.registry,
            self.policy,
            timeout_seconds=config.command_timeout_seconds,
            approvals=self.approvals,
            audit=self.audit,
        )
        self._lock = threading.RLock()
        self._seen_nonces: dict[str, int] = {}
        self._inflight: set[str] = set()
        self._completed: OrderedDict[str, tuple[str, dict[str, Any]]] = OrderedDict()

    def _prune(self, now: int) -> None:
        expired = [nonce for nonce, expires in self._seen_nonces.items() if expires <= now]
        for nonce in expired:
            self._seen_nonces.pop(nonce, None)
        while len(self._completed) > 512:
            self._completed.popitem(last=False)

    def health(self) -> dict[str, Any]:
        tools = {}
        ready_count = 0
        for adapter in self.registry:
            readiness = adapter.readiness()
            tools[adapter.spec.name] = {"ready": readiness.ready, "code": readiness.code}
            ready_count += int(readiness.ready)
        with self._lock:
            inflight = len(self._inflight)
        return {
            "ok": True,
            "worker": {
                "id": self.worker_id,
                "region": self.region,
                "tags": list(self.tags),
                "version": __version__,
            },
            "tools": tools,
            "ready_tools": ready_count,
            "total_tools": len(tools),
            "scope_rules": len(self.scope.allowed),
            "capacity": {
                "inflight": inflight,
                "max_concurrency": self.max_concurrency,
                "available_slots": max(0, self.max_concurrency - inflight),
                "accepting_jobs": inflight < self.max_concurrency,
            },
            "governance": {
                "local_scope_check": True,
                "local_policy_check": True,
                "arbitrary_shell": False,
                "approval_token_received": False,
                "argv_received": False,
                "hard_concurrency_limit": True,
            },
        }

    @staticmethod
    def _outcome_payload(outcome, *, worker_id: str, region: str, tags: tuple[str, ...], job_id: str) -> dict[str, Any]:
        evidence = outcome.evidence
        return {
            "ok": True,
            "job_id": job_id,
            "worker": {"id": worker_id, "region": region, "tags": list(tags)},
            "result": {
                "tool": outcome.result.tool,
                "success": outcome.result.success,
                "summary": outcome.result.summary,
                "evidence": dict(outcome.result.evidence),
            },
            "evidence": {
                "id": evidence.id,
                "tool": evidence.tool,
                "target": evidence.target,
                "argv": list(evidence.argv),
                "exit_code": evidence.exit_code,
                "stdout": evidence.stdout,
                "stderr": evidence.stderr,
                "started_at": evidence.started_at.isoformat(),
                "finished_at": evidence.finished_at.isoformat(),
            },
            "worker_policy": {
                "decision": outcome.policy.decision.value,
                "reason": outcome.policy.reason,
            },
        }

    def execute(self, payload: Mapping[str, Any], *, now: int | None = None) -> dict[str, Any]:
        envelope = DispatchEnvelope.from_dict(payload)
        envelope.verify(self.secret, expected_worker_id=self.worker_id, now=now)
        if envelope.control_decision not in {Decision.ALLOW.value, Decision.REQUIRE_APPROVAL.value}:
            raise PermissionError("control plane did not authorize this dispatch")
        if envelope.control_decision == Decision.REQUIRE_APPROVAL.value and not envelope.approval_granted:
            raise PermissionError("signed dispatch is missing the control-plane approval claim")
        if envelope.control_decision == Decision.ALLOW.value and envelope.approval_granted:
            raise PermissionError("signed dispatch contains an inconsistent approval claim")

        current_int = int(time.time() if now is None else now)
        with self._lock:
            self._prune(current_int)
            cached = self._completed.get(envelope.job_id)
            if cached is not None:
                signature, response = cached
                if signature != envelope.signature:
                    raise PermissionError("job id was already used with a different signature")
                replay = dict(response)
                replay["idempotent_replay"] = True
                return replay
            if envelope.job_id in self._inflight:
                raise RuntimeError("worker job is already in progress")
            if len(self._inflight) >= self.max_concurrency:
                raise WorkerBusy("worker concurrency limit reached")
            if envelope.nonce in self._seen_nonces:
                raise PermissionError("dispatch nonce has already been used")
            self._seen_nonces[envelope.nonce] = envelope.expires_at
            self._inflight.add(envelope.job_id)

        try:
            request = ToolRequest(
                tool=envelope.tool,
                target=envelope.target,
                parameters=dict(envelope.parameters),
                context={**dict(envelope.context), "remote_job_id": envelope.job_id, "worker_id": self.worker_id},
            )
            adapter = self.registry.get(request.tool)
            adapter.validate(request)
            local_decision = self.policy.evaluate(adapter.spec, request)
            if local_decision.decision is Decision.DENY:
                raise PermissionError(local_decision.reason)
            if local_decision.decision is Decision.REQUIRE_APPROVAL and not envelope.approval_granted:
                raise PermissionError("worker policy requires a control-plane approval grant")

            readiness = adapter.readiness()
            if not readiness.ready:
                raise RuntimeError(f"worker tool preflight blocked: {readiness.detail}")

            local_token = None
            if local_decision.decision is Decision.REQUIRE_APPROVAL:
                if request.target is None:
                    raise PermissionError("approval-bound worker request requires a target")
                local_token = self.approvals.issue(tool=request.tool, target=request.target, ttl_seconds=60).token
            outcome = self.executor.execute(request, approval_token=local_token)
            response = self._outcome_payload(
                outcome,
                worker_id=self.worker_id,
                region=self.region,
                tags=self.tags,
                job_id=envelope.job_id,
            )
            with self._lock:
                self._completed[envelope.job_id] = (envelope.signature, dict(response))
                self._completed.move_to_end(envelope.job_id)
                self._prune(current_int)
            return response
        except ExecutionDenied as exc:
            raise PermissionError(str(exc)) from exc
        finally:
            with self._lock:
                self._inflight.discard(envelope.job_id)


class WorkerHTTPServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, service: WorkerService):
        self.service = service
        super().__init__(address, WorkerHandler)


class WorkerHandler(BaseHTTPRequestHandler):
    server_version = "TONMEN-Worker"
    sys_version = ""

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        return

    def _json(self, status: int, payload: Mapping[str, Any]) -> None:
        data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        path = urlparse(self.path).path.rstrip("/") or "/"
        if path == "/v1/health":
            self._json(200, self.server.service.health())
            return
        self._json(404, {"ok": False, "error": "not found"})

    def do_POST(self) -> None:
        path = urlparse(self.path).path.rstrip("/") or "/"
        if path != "/v1/execute":
            self._json(404, {"ok": False, "error": "not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length <= 0 or length > 1024 * 1024:
            self._json(413, {"ok": False, "error": "invalid dispatch body size"})
            return
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("dispatch body must be an object")
            response = self.server.service.execute(payload)
            self._json(200, response)
        except PermissionError as exc:
            self._json(403, {"ok": False, "error": str(exc)[:500]})
        except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            self._json(400, {"ok": False, "error": str(exc)[:500]})
        except WorkerBusy as exc:
            self._json(429, {"ok": False, "error": str(exc)[:500], "retryable_before_execution": True})
        except RuntimeError as exc:
            status = 409 if "already in progress" in str(exc) else 503
            self._json(status, {"ok": False, "error": str(exc)[:500]})
        except Exception:
            self._json(500, {"ok": False, "error": "worker execution failed"})


def serve_worker(
    config: TonmenConfig,
    *,
    worker_id: str,
    secret: str,
    host: str = "127.0.0.1",
    port: int = 8890,
    region: str = "default",
    tags: tuple[str, ...] = (),
    max_concurrency: int = 4,
    allow_remote_bind: bool = False,
) -> int:
    bind_host = validate_worker_bind_host(host, allow_remote=allow_remote_bind)
    if not 1 <= int(port) <= 65535:
        raise ValueError("worker port must be within 1-65535")
    service = WorkerService(
        config,
        worker_id=worker_id,
        secret=secret,
        region=region,
        tags=tags,
        max_concurrency=max_concurrency,
    )
    server = WorkerHTTPServer((bind_host, int(port)), service)
    print(f"TONMEN Worker {service.worker_id}: http://{bind_host}:{server.server_address[1]}")
    print(f"Concurrency: {service.max_concurrency}; signed typed adapter jobs only; arbitrary shell disabled.")
    if bind_host not in _LOOPBACK_HOSTS:
        print("Remote bind enabled: keep this listener on a private/firewalled encrypted network.")
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        print("\nTONMEN Worker stopped.")
    finally:
        server.server_close()
    return 0
