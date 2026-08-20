from __future__ import annotations

import os
import time
from datetime import datetime
from typing import Any, Mapping

from tonmen.audit import AuditLog
from tonmen.evidence import EvidenceRecord
from tonmen.events import EventBus
from tonmen.execution import ExecutionDenied, ExecutionOutcome
from tonmen.policy import ApprovalStore, Decision, PolicyDecision, PolicyEngine
from tonmen.tools import ToolRegistry, ToolRequest, ToolResult

from .pool import WorkerPool, WorkerSpec
from .protocol import DispatchEnvelope
from .scheduler import WorkerLease, WorkerScheduler
from .transport import WorkerHTTPTransport, WorkerTransportError

_SAFE_CONTEXT_KEYS = {
    "mission_id",
    "plan_id",
    "step_id",
    "worker_id",
    "worker_region",
    "worker_tags",
}


class RemoteWorkerExecutor:
    """Governed control-plane executor with bounded remote Worker scheduling.

    Scope / risk / Approval remain central. The scheduler only chooses an eligible
    execution slot. Health-gated selection may choose another worker before POST.
    Once POST starts, transport ambiguity fails closed: the same job is never
    automatically executed on a second worker.
    """

    def __init__(
        self,
        registry: ToolRegistry,
        policy: PolicyEngine,
        pool: WorkerPool,
        *,
        timeout_seconds: int = 120,
        approvals: ApprovalStore | None = None,
        audit: AuditLog | None = None,
        events: EventBus | None = None,
        transport: WorkerHTTPTransport | None = None,
        scheduler: WorkerScheduler | None = None,
    ) -> None:
        if not pool.workers:
            raise ValueError("worker execution mode requires at least one TONMEN_WORKERS entry")
        self.registry = registry
        self.policy = policy
        self.pool = pool
        self.timeout_seconds = int(timeout_seconds)
        self.approvals = approvals
        self.audit = audit
        self.events = events
        self.transport = transport or WorkerHTTPTransport(timeout_seconds=max(15, self.timeout_seconds + 30))
        self.probe_before_dispatch = os.getenv("TONMEN_WORKER_PROBE_BEFORE_DISPATCH", "1").strip() != "0"
        self.job_ttl_seconds = max(5, min(300, int(os.getenv("TONMEN_WORKER_JOB_TTL_SECONDS", "60") or "60")))
        queue_timeout = float(os.getenv("TONMEN_WORKER_QUEUE_TIMEOUT_SECONDS", "30") or "30")
        max_queue = int(os.getenv("TONMEN_WORKER_MAX_QUEUE", "128") or "128")
        self.scheduler = scheduler or WorkerScheduler(
            pool,
            queue_timeout_seconds=queue_timeout,
            max_queue_size=max_queue,
        )

    @property
    def uses_local_subprocess(self) -> bool:
        return False

    @property
    def mode(self) -> str:
        return "worker"

    @property
    def worker_count(self) -> int:
        return len(self.pool.workers)

    def _emit(self, event_type: str, request: ToolRequest, **data: object) -> None:
        if self.events is None:
            return
        payload = {key: value for key, value in request.context.items() if key in _SAFE_CONTEXT_KEYS}
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

    @staticmethod
    def _safe_context(request: ToolRequest) -> dict[str, Any]:
        return {key: value for key, value in request.context.items() if key in _SAFE_CONTEXT_KEYS}

    def _health_allows(self, spec: WorkerSpec, request: ToolRequest) -> bool:
        try:
            health = dict(self.transport.health(spec, timeout=5))
        except Exception as exc:
            self.pool.record_failure(spec.id, str(exc))
            self._emit("worker.unavailable", request, worker_id=spec.id, worker_region=spec.region, reason=str(exc)[:300])
            return False
        self.pool.record_health(spec.id, health)
        worker = health.get("worker") if isinstance(health.get("worker"), dict) else {}
        if str(worker.get("id") or "").strip().lower() != spec.id:
            self.pool.record_failure(spec.id, "worker health identity mismatch")
            return False
        tools = health.get("tools") if isinstance(health.get("tools"), dict) else {}
        tool_state = tools.get(request.tool) if isinstance(tools.get(request.tool), dict) else {}
        if not bool(tool_state.get("ready")):
            self._emit("worker.tool_unavailable", request, worker_id=spec.id, worker_region=spec.region)
            return False
        capacity = health.get("capacity") if isinstance(health.get("capacity"), dict) else {}
        if capacity and not bool(capacity.get("accepting_jobs", True)):
            self._emit(
                "worker.capacity_unavailable",
                request,
                worker_id=spec.id,
                worker_region=spec.region,
                inflight=int(capacity.get("inflight") or 0),
                max_concurrency=int(capacity.get("max_concurrency") or spec.max_concurrency),
            )
            return False
        return True

    def _acquire_worker(self, request: ToolRequest) -> WorkerLease:
        excluded: set[str] = set()
        deadline = time.monotonic() + self.scheduler.queue_timeout_seconds
        self._emit(
            "worker.queue_entered",
            request,
            queue_depth=self.scheduler.public_status()["queue_depth"],
        )
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise RuntimeError("timed out finding a healthy worker execution slot")
            lease = self.scheduler.acquire(
                request,
                timeout_seconds=remaining,
                exclude_worker_ids=excluded,
            )
            spec = lease.worker
            if not self.probe_before_dispatch or self._health_allows(spec, request):
                self._emit(
                    "worker.slot_acquired",
                    request,
                    worker_id=spec.id,
                    worker_region=spec.region,
                    queued_ms=lease.queued_ms,
                    inflight=self.pool.state[spec.id].inflight,
                    max_concurrency=spec.max_concurrency,
                )
                return lease
            self.scheduler.release(lease)
            excluded.add(spec.id)
            self._emit(
                "worker.slot_rejected",
                request,
                worker_id=spec.id,
                worker_region=spec.region,
                reason="pre-dispatch health/readiness/capacity check failed",
            )

    @staticmethod
    def _parse_datetime(value: object) -> datetime:
        if not isinstance(value, str):
            raise WorkerTransportError("worker evidence timestamp is missing")
        return datetime.fromisoformat(value)

    @classmethod
    def _outcome_from_payload(cls, payload: Mapping[str, Any], central_policy: PolicyDecision) -> ExecutionOutcome:
        result_payload = payload.get("result") if isinstance(payload.get("result"), dict) else None
        evidence_payload = payload.get("evidence") if isinstance(payload.get("evidence"), dict) else None
        worker_payload = payload.get("worker") if isinstance(payload.get("worker"), dict) else {}
        if result_payload is None or evidence_payload is None:
            raise WorkerTransportError("worker response is missing result/evidence")
        evidence = EvidenceRecord(
            id=str(evidence_payload.get("id") or ""),
            tool=str(evidence_payload.get("tool") or result_payload.get("tool") or ""),
            target=evidence_payload.get("target") if evidence_payload.get("target") is None else str(evidence_payload.get("target")),
            argv=tuple(str(item) for item in evidence_payload.get("argv", []) if str(item)),
            exit_code=int(evidence_payload.get("exit_code", -1)),
            stdout=str(evidence_payload.get("stdout") or ""),
            stderr=str(evidence_payload.get("stderr") or ""),
            started_at=cls._parse_datetime(evidence_payload.get("started_at")),
            finished_at=cls._parse_datetime(evidence_payload.get("finished_at")),
        )
        if not evidence.id or not evidence.tool or not evidence.argv:
            raise WorkerTransportError("worker returned incomplete execution evidence")
        worker_id = str(worker_payload.get("id") or "")
        metadata = dict(result_payload.get("evidence") or {}) if isinstance(result_payload.get("evidence"), dict) else {}
        metadata.update(
            {
                "id": evidence.id,
                "exit_code": evidence.exit_code,
                "worker_id": worker_id,
                "worker_region": str(worker_payload.get("region") or "default"),
                "worker_tags": list(worker_payload.get("tags") or []),
                "remote_job_id": str(payload.get("job_id") or ""),
                "remote_execution": True,
            }
        )
        result = ToolResult(
            tool=str(result_payload.get("tool") or evidence.tool),
            success=bool(result_payload.get("success")),
            summary=str(result_payload.get("summary") or "remote execution completed"),
            evidence=metadata,
        )
        return ExecutionOutcome(result=result, evidence=evidence, policy=central_policy)

    def execute(self, request: ToolRequest, *, approval_token: str | None = None) -> ExecutionOutcome:
        adapter = self.registry.get(request.tool)
        adapter.validate(request)
        decision = self.policy.evaluate(adapter.spec, request)
        if decision.decision is Decision.DENY:
            self._audit(request, "deny", decision.reason)
            self._emit("tool.denied", request, reason=decision.reason)
            raise ExecutionDenied(decision.reason)

        if decision.decision is Decision.REQUIRE_APPROVAL and not approval_token:
            message = "higher-risk action requires approval grant"
            self._audit(request, "deny", message)
            self._emit("tool.approval_required", request, reason=message)
            raise ExecutionDenied(message)

        lease = self._acquire_worker(request)
        spec = lease.worker
        try:
            approval_granted = False
            if decision.decision is Decision.REQUIRE_APPROVAL:
                grant = self.approvals.consume(approval_token, request) if self.approvals else None
                if grant is None:
                    message = "higher-risk action requires a valid single-use approval grant"
                    self._audit(request, "deny", message)
                    self._emit("tool.approval_required", request, reason=message)
                    raise ExecutionDenied(message)
                approval_granted = True

            envelope = DispatchEnvelope.issue(
                worker_id=spec.id,
                tool=request.tool,
                target=request.target,
                parameters=request.parameters,
                context=self._safe_context(request),
                approval_granted=approval_granted,
                control_decision=decision.decision.value,
                control_reason=decision.reason,
                secret=spec.secret(),
                ttl_seconds=self.job_ttl_seconds,
            )
            self._emit(
                "worker.dispatch_started",
                request,
                worker_id=spec.id,
                worker_region=spec.region,
                remote_job_id=envelope.job_id,
                approval_forwarded=False,
                argv_forwarded=False,
            )
            try:
                payload = self.transport.dispatch(spec, envelope)
                outcome = self._outcome_from_payload(payload, decision)
            except Exception as exc:
                self.pool.record_failure(spec.id, str(exc))
                message = str(exc)[:500]
                self._audit(request, "error", f"worker {spec.id}: {message}")
                self._emit(
                    "worker.dispatch_failed",
                    request,
                    worker_id=spec.id,
                    worker_region=spec.region,
                    remote_job_id=envelope.job_id,
                    reason=message,
                    automatic_cross_worker_retry=False,
                )
                raise

            self.pool.record_success(spec.id)
            self._audit(request, "allow" if outcome.result.success else "error", f"worker {spec.id}: {outcome.result.summary}", outcome.evidence.id)
            self._emit(
                "worker.dispatch_completed",
                request,
                worker_id=spec.id,
                worker_region=spec.region,
                remote_job_id=envelope.job_id,
                evidence_id=outcome.evidence.id,
                exit_code=outcome.evidence.exit_code,
                success=outcome.result.success,
            )
            return outcome
        finally:
            self.scheduler.release(lease)
            self._emit(
                "worker.slot_released",
                request,
                worker_id=spec.id,
                worker_region=spec.region,
                inflight=self.pool.state[spec.id].inflight,
                max_concurrency=spec.max_concurrency,
            )
