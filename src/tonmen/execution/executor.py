from __future__ import annotations

import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable
from uuid import uuid4

from tonmen.audit import AuditLog
from tonmen.evidence import EvidenceRecord
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
    """Normalize TimeoutExpired output/stderr without losing partial evidence."""
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
    ) -> None:
        self.registry = registry
        self.policy = policy
        self.timeout_seconds = timeout_seconds
        self._runner = runner
        self.approvals = approvals
        self.audit = audit

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

    def execute(self, request: ToolRequest, *, approval_token: str | None = None) -> ExecutionOutcome:
        adapter = self.registry.get(request.tool)
        adapter.validate(request)
        decision = self.policy.evaluate(adapter.spec, request)
        if decision.decision is Decision.DENY:
            self._audit(request, "deny", decision.reason)
            raise ExecutionDenied(decision.reason)
        if decision.decision is Decision.REQUIRE_APPROVAL:
            grant = None
            if approval_token and self.approvals is not None:
                grant = self.approvals.consume(approval_token, request)
            if grant is None:
                self._audit(request, "deny", "higher-risk action requires approval grant")
                raise ExecutionDenied("higher-risk action requires approval grant")

        argv = tuple(str(value) for value in adapter.build_argv(request))
        if not argv or any(not value for value in argv):
            raise ValueError("adapter produced invalid argv")

        started = datetime.now(timezone.utc)
        try:
            completed = self._runner(
                list(argv),
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=False,
                shell=False,
            )
        except subprocess.TimeoutExpired as exc:
            finished = datetime.now(timezone.utc)
            timeout_seconds = int(exc.timeout) if exc.timeout is not None else self.timeout_seconds
            stdout = _timeout_text(exc.output)
            stderr = _timeout_text(exc.stderr)
            timeout_message = f"execution timed out after {timeout_seconds} seconds"
            if stderr:
                stderr = f"{stderr.rstrip()}\n{timeout_message}\n"
            else:
                stderr = timeout_message + "\n"
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
            result = ToolResult(
                tool=adapter.spec.name,
                success=False,
                summary=timeout_message,
                evidence={
                    "id": evidence.id,
                    "exit_code": evidence.exit_code,
                    "timed_out": True,
                    "timeout_seconds": timeout_seconds,
                },
            )
            self._audit(request, "timeout", timeout_message, evidence.id)
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
        result = ToolResult(
            tool=adapter.spec.name,
            success=success,
            summary="execution completed" if success else f"execution exited with code {completed.returncode}",
            evidence={"id": evidence.id, "exit_code": evidence.exit_code, "timed_out": False},
        )
        self._audit(request, "allow" if success else "error", result.summary, evidence.id)
        return ExecutionOutcome(result=result, evidence=evidence, policy=decision)
