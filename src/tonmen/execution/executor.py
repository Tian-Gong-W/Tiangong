from __future__ import annotations

import subprocess
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Mapping
from uuid import uuid4

from tonmen.audit import AuditLog
from tonmen.evidence import EvidenceRecord
from tonmen.events import EventBus
from tonmen.policy import ApprovalStore, Decision, PolicyDecision, PolicyEngine
from tonmen.tools import ToolRegistry, ToolRequest, ToolResult


class ExecutionDenied(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ExecutionOutcome:
    result: ToolResult
    evidence: EvidenceRecord
    policy: PolicyDecision


def _timeout_text(value: object | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


class ToolExecutor:
    """Executes adapter argv with shell=False after scope, risk and approval checks."""

    def __init__(
        self,
        registry: ToolRegistry,
        policy: PolicyEngine,
        timeout_seconds: int = 120,
        runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
        approvals: ApprovalStore | None = None,
        audit: AuditLog | None = None,
        events: EventBus | None = None,
        tool_timeouts: Mapping[str, int] | None = None,
    ) -> None:
        self.registry = registry
        self.policy = policy
        self.timeout_seconds = int(timeout_seconds)
        self.tool_timeouts = {
            str(name).strip().lower(): int(seconds)
            for name, seconds in (tool_timeouts or {}).items()
            if str(name).strip() and int(seconds) > 0
        }
        self._runner = runner
        self.approvals = approvals
        self.audit = audit
        self.events = events

    @property
    def uses_local_subprocess(self) -> bool:
        """True when this executor will invoke local binaries through the production backend."""
        return self._runner is subprocess.run

    def timeout_for(self, tool: str) -> int:
        return int(self.tool_timeouts.get(str(tool).strip().lower(), self.timeout_seconds))

    def _emit(self, event_type: str, request: ToolRequest, **data: object) -> None:
        if self.events is not None:
            payload = dict(request.context)
            payload.update(data)
            self.events.publish(event_type, tool=request.tool, target=request.target, **payload)

    def _audit(self, request: ToolRequest, decision: str, message: str, evidence_id: str | None = None) -> None:
        if self.audit is not None:
            self.audit.append(action="tool.execute", tool=request.tool, target=request.target,
                              decision=decision, message=message, evidence_id=evidence_id)

    def _run_streaming(
        self,
        argv: tuple[str, ...],
        request: ToolRequest,
        *,
        timeout_seconds: int,
    ) -> subprocess.CompletedProcess[str]:
        process = subprocess.Popen(list(argv), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   text=True, bufsize=1, shell=False)
        stdout_parts: list[str] = []
        stderr_parts: list[str] = []

        def drain(pipe, stream: str, sink: list[str]) -> None:
            if pipe is None:
                return
            try:
                for chunk in iter(pipe.readline, ""):
                    if not chunk:
                        break
                    sink.append(chunk)
                    self._emit("tool.output", request, stream=stream, chunk=chunk)
            finally:
                try:
                    pipe.close()
                except OSError:
                    pass

        stdout_thread = threading.Thread(target=drain, args=(process.stdout, "stdout", stdout_parts), daemon=True)
        stderr_thread = threading.Thread(target=drain, args=(process.stderr, "stderr", stderr_parts), daemon=True)
        stdout_thread.start(); stderr_thread.start()
        try:
            returncode = process.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired as exc:
            process.kill(); process.wait()
            stdout_thread.join(timeout=1.0); stderr_thread.join(timeout=1.0)
            raise subprocess.TimeoutExpired(cmd=list(argv), timeout=exc.timeout,
                                            output="".join(stdout_parts), stderr="".join(stderr_parts)) from exc
        stdout_thread.join(timeout=1.0); stderr_thread.join(timeout=1.0)
        return subprocess.CompletedProcess(list(argv), int(returncode),
                                           stdout="".join(stdout_parts), stderr="".join(stderr_parts))

    def execute(self, request: ToolRequest, *, approval_token: str | None = None) -> ExecutionOutcome:
        adapter = self.registry.get(request.tool)
        adapter.validate(request)
        decision = self.policy.evaluate(adapter.spec, request)
        if decision.decision is Decision.DENY:
            self._audit(request, "deny", decision.reason); self._emit("tool.denied", request, reason=decision.reason)
            raise ExecutionDenied(decision.reason)
        if decision.decision is Decision.REQUIRE_APPROVAL:
            grant = self.approvals.consume(approval_token, request) if approval_token and self.approvals else None
            if grant is None:
                message = "higher-risk action requires approval grant"
                self._audit(request, "deny", message); self._emit("tool.approval_required", request, reason=message)
                raise ExecutionDenied(message)

        argv = tuple(str(value) for value in adapter.build_argv(request))
        if not argv or any(not value for value in argv):
            raise ValueError("adapter produced invalid argv")

        effective_timeout = self.timeout_for(adapter.spec.name)
        started = datetime.now(timezone.utc)
        self._emit("tool.started", request, argv=list(argv), timeout_seconds=effective_timeout)
        try:
            if self._runner is subprocess.run:
                completed = self._run_streaming(argv, request, timeout_seconds=effective_timeout)
            else:
                completed = self._runner(list(argv), capture_output=True, text=True,
                                         timeout=effective_timeout, check=False, shell=False)
        except subprocess.TimeoutExpired as exc:
            finished = datetime.now(timezone.utc)
            timeout_seconds = int(exc.timeout) if exc.timeout is not None else effective_timeout
            stdout, stderr = _timeout_text(exc.output), _timeout_text(exc.stderr)
            timeout_message = f"execution timed out after {timeout_seconds} seconds"
            stderr = f"{stderr.rstrip()}\n{timeout_message}\n" if stderr else timeout_message + "\n"
            evidence = EvidenceRecord(id=uuid4().hex, tool=adapter.spec.name, target=request.target,
                                      argv=argv, exit_code=124, stdout=stdout, stderr=stderr,
                                      started_at=started, finished_at=finished)
            result = ToolResult(tool=adapter.spec.name, success=False, summary=timeout_message,
                                evidence={"id": evidence.id, "exit_code": 124, "timed_out": True,
                                          "timeout_seconds": timeout_seconds})
            self._audit(request, "timeout", timeout_message, evidence.id)
            self._emit("tool.timeout", request, evidence_id=evidence.id, exit_code=124,
                       timeout_seconds=timeout_seconds)
            return ExecutionOutcome(result=result, evidence=evidence, policy=decision)

        finished = datetime.now(timezone.utc)
        evidence = EvidenceRecord(id=uuid4().hex, tool=adapter.spec.name, target=request.target,
                                  argv=argv, exit_code=int(completed.returncode), stdout=completed.stdout or "",
                                  stderr=completed.stderr or "", started_at=started, finished_at=finished)
        success = completed.returncode == 0
        result = ToolResult(tool=adapter.spec.name, success=success,
                            summary="execution completed" if success else f"execution exited with code {completed.returncode}",
                            evidence={"id": evidence.id, "exit_code": evidence.exit_code, "timed_out": False,
                                      "timeout_seconds": effective_timeout})
        self._audit(request, "allow" if success else "error", result.summary, evidence.id)
        self._emit("tool.completed" if success else "tool.failed", request,
                   evidence_id=evidence.id, exit_code=evidence.exit_code, success=success,
                   timeout_seconds=effective_timeout)
        return ExecutionOutcome(result=result, evidence=evidence, policy=decision)
