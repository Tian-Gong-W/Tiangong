from __future__ import annotations

import subprocess
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable
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


def _bounded_text(value: object | None, max_bytes: int) -> tuple[str, bool]:
    text = _timeout_text(value)
    encoded = text.encode("utf-8", errors="replace")
    if len(encoded) <= max_bytes:
        return text, False
    clipped = encoded[:max_bytes].decode("utf-8", errors="ignore")
    marker = f"\n[TONMEN output truncated at {max_bytes} bytes]\n"
    return clipped + marker, True


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
        max_output_bytes: int = 2_097_152,
    ) -> None:
        if int(max_output_bytes) < 65_536:
            raise ValueError("max_output_bytes must be at least 65536")
        self.registry = registry
        self.policy = policy
        self.timeout_seconds = timeout_seconds
        self.max_output_bytes = int(max_output_bytes)
        self._runner = runner
        self.approvals = approvals
        self.audit = audit
        self.events = events

    @property
    def uses_local_subprocess(self) -> bool:
        """True when this executor will invoke local binaries through the production backend."""
        return self._runner is subprocess.run

    def _emit(self, event_type: str, request: ToolRequest, **data: object) -> None:
        if self.events is not None:
            payload = dict(request.context)
            payload.update(data)
            self.events.publish(event_type, tool=request.tool, target=request.target, **payload)

    def _audit(self, request: ToolRequest, decision: str, message: str, evidence_id: str | None = None) -> None:
        if self.audit is not None:
            self.audit.append(
                action="tool.execute",
                tool=request.tool,
                target=request.target,
                decision=decision,
                message=message,
                evidence_id=evidence_id,
            )

    def _effective_timeout(self, request: ToolRequest, adapter) -> float:
        # A typed ToolSpec may request a wider process budget than the generic
        # discovery-oriented executor default. Mission remaining time still wins.
        typed = adapter.spec.execution_timeout_seconds
        timeout = float(typed if typed is not None else self.timeout_seconds)
        raw = request.context.get("execution_timeout_seconds")
        if raw is None:
            return timeout
        try:
            requested = float(raw)
        except (TypeError, ValueError):
            return timeout
        if requested <= 0:
            return 0.001
        return min(timeout, requested)

    def _run_streaming(
        self,
        argv: tuple[str, ...],
        request: ToolRequest,
        *,
        timeout_seconds: float,
    ) -> tuple[subprocess.CompletedProcess[str], dict[str, bool]]:
        process = subprocess.Popen(
            list(argv),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            shell=False,
        )
        stdout_parts: list[str] = []
        stderr_parts: list[str] = []
        truncated = {"stdout": False, "stderr": False}

        def drain(pipe, stream: str, sink: list[str]) -> None:
            if pipe is None:
                return
            used = 0
            try:
                for chunk in iter(pipe.readline, ""):
                    if not chunk:
                        break
                    if used >= self.max_output_bytes:
                        truncated[stream] = True
                        continue
                    encoded = chunk.encode("utf-8", errors="replace")
                    remaining = self.max_output_bytes - used
                    if len(encoded) > remaining:
                        visible = encoded[:remaining].decode("utf-8", errors="ignore")
                        if visible:
                            sink.append(visible)
                            self._emit("tool.output", request, stream=stream, chunk=visible)
                        used = self.max_output_bytes
                        truncated[stream] = True
                        continue
                    sink.append(chunk)
                    used += len(encoded)
                    self._emit("tool.output", request, stream=stream, chunk=chunk)
            finally:
                try:
                    pipe.close()
                except OSError:
                    pass

        stdout_thread = threading.Thread(target=drain, args=(process.stdout, "stdout", stdout_parts), daemon=True)
        stderr_thread = threading.Thread(target=drain, args=(process.stderr, "stderr", stderr_parts), daemon=True)
        stdout_thread.start()
        stderr_thread.start()
        try:
            returncode = process.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired as exc:
            process.kill()
            process.wait()
            stdout_thread.join(timeout=1.0)
            stderr_thread.join(timeout=1.0)
            stdout = "".join(stdout_parts)
            stderr = "".join(stderr_parts)
            if truncated["stdout"]:
                stdout += f"\n[TONMEN output truncated at {self.max_output_bytes} bytes]\n"
            if truncated["stderr"]:
                stderr += f"\n[TONMEN output truncated at {self.max_output_bytes} bytes]\n"
            error = subprocess.TimeoutExpired(cmd=list(argv), timeout=exc.timeout, output=stdout, stderr=stderr)
            error.output_truncated = bool(truncated["stdout"] or truncated["stderr"])
            error.stdout_truncated = bool(truncated["stdout"])
            error.stderr_truncated = bool(truncated["stderr"])
            raise error from exc
        stdout_thread.join(timeout=1.0)
        stderr_thread.join(timeout=1.0)
        stdout = "".join(stdout_parts)
        stderr = "".join(stderr_parts)
        if truncated["stdout"]:
            stdout += f"\n[TONMEN output truncated at {self.max_output_bytes} bytes]\n"
        if truncated["stderr"]:
            stderr += f"\n[TONMEN output truncated at {self.max_output_bytes} bytes]\n"
        return (
            subprocess.CompletedProcess(list(argv), int(returncode), stdout=stdout, stderr=stderr),
            truncated,
        )

    def execute(self, request: ToolRequest, *, approval_token: str | None = None) -> ExecutionOutcome:
        adapter = self.registry.get(request.tool)
        adapter.validate(request)
        decision = self.policy.evaluate(adapter.spec, request)
        if decision.decision is Decision.DENY:
            self._audit(request, "deny", decision.reason)
            self._emit("tool.denied", request, reason=decision.reason)
            raise ExecutionDenied(decision.reason)

        build_request = request
        if self.uses_local_subprocess:
            readiness = adapter.readiness()
            if not readiness.ready:
                message = f"tool preflight blocked: {readiness.detail}"
                self._audit(request, "deny", message)
                self._emit(
                    "tool.preflight_blocked",
                    request,
                    code=readiness.code,
                    detail=readiness.detail,
                    remediation=readiness.remediation,
                )
                raise ExecutionDenied(message)
            verified_path = readiness.metadata.get("path") or readiness.metadata.get("binary")
            if verified_path:
                context = dict(request.context)
                context["_verified_binary_path"] = str(verified_path)
                build_request = ToolRequest(
                    tool=request.tool,
                    target=request.target,
                    parameters=request.parameters,
                    context=context,
                )

        # Readiness/identity is checked before consuming a one-shot approval token.
        if decision.decision is Decision.REQUIRE_APPROVAL:
            grant = self.approvals.consume(approval_token, request) if approval_token and self.approvals else None
            if grant is None:
                message = "higher-risk action requires approval grant"
                self._audit(request, "deny", message)
                self._emit("tool.approval_required", request, reason=message)
                raise ExecutionDenied(message)

        argv = tuple(str(value) for value in adapter.build_argv(build_request))
        if not argv or any(not value for value in argv):
            raise ValueError("adapter produced invalid argv")

        effective_timeout = self._effective_timeout(request, adapter)
        started = datetime.now(timezone.utc)
        self._emit(
            "tool.started",
            request,
            argv=list(argv),
            timeout_seconds=effective_timeout,
            output_max_bytes_per_stream=self.max_output_bytes,
        )
        try:
            if self._runner is subprocess.run:
                completed, truncation = self._run_streaming(
                    argv,
                    request,
                    timeout_seconds=effective_timeout,
                )
            else:
                completed = self._runner(
                    list(argv),
                    capture_output=True,
                    text=True,
                    timeout=effective_timeout,
                    check=False,
                    shell=False,
                )
                stdout, stdout_truncated = _bounded_text(completed.stdout, self.max_output_bytes)
                stderr, stderr_truncated = _bounded_text(completed.stderr, self.max_output_bytes)
                completed = subprocess.CompletedProcess(
                    completed.args,
                    completed.returncode,
                    stdout=stdout,
                    stderr=stderr,
                )
                truncation = {"stdout": stdout_truncated, "stderr": stderr_truncated}
        except subprocess.TimeoutExpired as exc:
            finished = datetime.now(timezone.utc)
            timeout_seconds = float(exc.timeout) if exc.timeout is not None else effective_timeout
            stdout, stdout_truncated = _bounded_text(exc.output, self.max_output_bytes)
            stderr, stderr_truncated = _bounded_text(exc.stderr, self.max_output_bytes)
            stdout_truncated = bool(stdout_truncated or getattr(exc, "stdout_truncated", False))
            stderr_truncated = bool(stderr_truncated or getattr(exc, "stderr_truncated", False))
            timeout_message = f"execution timed out after {timeout_seconds:g} seconds"
            stderr = f"{stderr.rstrip()}\n{timeout_message}\n" if stderr else timeout_message + "\n"
            evidence = EvidenceRecord(
                id=uuid4().hex,
                tool=adapter.spec.name,
                target=request.target,
                argv=argv,
                exit_code=124,
                stdout=stdout,
                stderr=stderr,
                started_at=started,
                finished_at=finished,
            )
            output_truncated = bool(stdout_truncated or stderr_truncated or getattr(exc, "output_truncated", False))
            result = ToolResult(
                tool=adapter.spec.name,
                success=False,
                summary=timeout_message,
                evidence={
                    "id": evidence.id,
                    "exit_code": 124,
                    "timed_out": True,
                    "timeout_seconds": timeout_seconds,
                    "output_truncated": output_truncated,
                    "stdout_truncated": stdout_truncated,
                    "stderr_truncated": stderr_truncated,
                    "output_max_bytes_per_stream": self.max_output_bytes,
                },
            )
            self._audit(request, "timeout", timeout_message, evidence.id)
            self._emit(
                "tool.timeout",
                request,
                evidence_id=evidence.id,
                exit_code=124,
                timeout_seconds=timeout_seconds,
                output_truncated=output_truncated,
            )
            return ExecutionOutcome(result=result, evidence=evidence, policy=decision)

        finished = datetime.now(timezone.utc)
        evidence = EvidenceRecord(
            id=uuid4().hex,
            tool=adapter.spec.name,
            target=request.target,
            argv=argv,
            exit_code=int(completed.returncode),
            stdout=completed.stdout or "",
            stderr=completed.stderr or "",
            started_at=started,
            finished_at=finished,
        )
        success = completed.returncode == 0
        output_truncated = bool(truncation["stdout"] or truncation["stderr"])
        result = ToolResult(
            tool=adapter.spec.name,
            success=success,
            summary="execution completed" if success else f"execution exited with code {completed.returncode}",
            evidence={
                "id": evidence.id,
                "exit_code": evidence.exit_code,
                "timed_out": False,
                "output_truncated": output_truncated,
                "stdout_truncated": bool(truncation["stdout"]),
                "stderr_truncated": bool(truncation["stderr"]),
                "output_max_bytes_per_stream": self.max_output_bytes,
            },
        )
        self._audit(request, "allow" if success else "error", result.summary, evidence.id)
        self._emit(
            "tool.completed" if success else "tool.failed",
            request,
            evidence_id=evidence.id,
            exit_code=evidence.exit_code,
            success=success,
            output_truncated=output_truncated,
        )
        return ExecutionOutcome(result=result, evidence=evidence, policy=decision)
