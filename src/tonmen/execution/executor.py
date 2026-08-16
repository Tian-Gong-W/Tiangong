from __future__ import annotations

import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable
from uuid import uuid4

from tonmen.evidence import EvidenceRecord
from tonmen.policy import Decision, PolicyDecision, PolicyEngine
from tonmen.tools import ToolRegistry, ToolRequest, ToolResult


class ExecutionDenied(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ExecutionOutcome:
    result: ToolResult
    evidence: EvidenceRecord
    policy: PolicyDecision


class ToolExecutor:
    """Executes only adapter-produced argv with shell=False."""

    def __init__(
        self,
        registry: ToolRegistry,
        policy: PolicyEngine,
        timeout_seconds: int = 120,
        runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    ) -> None:
        self.registry = registry
        self.policy = policy
        self.timeout_seconds = timeout_seconds
        self._runner = runner

    def execute(self, request: ToolRequest, *, approved: bool = False) -> ExecutionOutcome:
        adapter = self.registry.get(request.tool)
        adapter.validate(request)
        decision = self.policy.evaluate(adapter.spec, request)
        if decision.decision is Decision.DENY:
            raise ExecutionDenied(decision.reason)
        if decision.decision is Decision.REQUIRE_APPROVAL and not approved:
            raise ExecutionDenied(decision.reason)

        argv = tuple(str(value) for value in adapter.build_argv(request))
        if not argv or any(not value for value in argv):
            raise ValueError("adapter produced invalid argv")

        started = datetime.now(timezone.utc)
        completed = self._runner(
            list(argv),
            capture_output=True,
            text=True,
            timeout=self.timeout_seconds,
            check=False,
            shell=False,
        )
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
            evidence={"id": evidence.id, "exit_code": evidence.exit_code},
        )
        return ExecutionOutcome(result=result, evidence=evidence, policy=decision)
