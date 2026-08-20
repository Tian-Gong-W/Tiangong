from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from tonmen.tools import ToolRequest

from .pool import WorkerPool, WorkerSpec


class WorkerQueueFull(RuntimeError):
    pass


class WorkerQueueTimeout(RuntimeError):
    pass


@dataclass(slots=True)
class QueueTicket:
    id: str
    request: ToolRequest
    enqueued_at: float
    excluded_worker_ids: set[str] = field(default_factory=set)


@dataclass(frozen=True, slots=True)
class WorkerLease:
    worker: WorkerSpec
    ticket_id: str
    queued_ms: int


class WorkerScheduler:
    """Thread-safe, bounded scheduler for remote execution slots.

    The scheduler controls where a governed request runs; it does not evaluate
    Scope, risk or Approval. Those checks stay in RemoteWorkerExecutor and on the
    worker itself. Drain stops new leases and never interrupts an inflight job.
    """

    def __init__(
        self,
        pool: WorkerPool,
        *,
        queue_timeout_seconds: float = 30.0,
        max_queue_size: int = 128,
    ) -> None:
        if queue_timeout_seconds <= 0:
            raise ValueError("worker queue timeout must be positive")
        if max_queue_size < 1 or max_queue_size > 10000:
            raise ValueError("worker max queue size must be within 1-10000")
        self.pool = pool
        self.queue_timeout_seconds = float(queue_timeout_seconds)
        self.max_queue_size = int(max_queue_size)
        self._condition = threading.Condition(threading.RLock())
        self._queue: deque[QueueTicket] = deque()
        self.total_enqueued = 0
        self.total_dispatched = 0
        self.total_timed_out = 0
        self.total_released = 0
        self.total_wait_ms = 0
        self.peak_queue_depth = 0

    def _available(self, ticket: QueueTicket) -> tuple[WorkerSpec, ...]:
        return self.pool.candidates(
            ticket.request,
            require_capacity=True,
            exclude_ids=ticket.excluded_worker_ids,
        )

    def _configured_route_exists(self, ticket: QueueTicket) -> bool:
        return bool(
            self.pool.candidates(
                ticket.request,
                include_draining=True,
                require_capacity=False,
                exclude_ids=ticket.excluded_worker_ids,
            )
        )

    def _has_priority(self, ticket: QueueTicket, selected: WorkerSpec) -> bool:
        """Allow bypass only when earlier tickets cannot use this free worker.

        This avoids needless head-of-line blocking between disjoint region/tag
        routes while preserving FIFO order for tickets competing for one worker.
        """
        for queued in self._queue:
            if queued is ticket:
                return True
            earlier = self.pool.candidates(
                queued.request,
                require_capacity=True,
                exclude_ids=queued.excluded_worker_ids,
            )
            if any(item.id == selected.id for item in earlier):
                return False
        return True

    def acquire(
        self,
        request: ToolRequest,
        *,
        timeout_seconds: float | None = None,
        exclude_worker_ids: set[str] | None = None,
    ) -> WorkerLease:
        timeout = self.queue_timeout_seconds if timeout_seconds is None else float(timeout_seconds)
        if timeout <= 0:
            raise ValueError("worker queue timeout must be positive")
        ticket = QueueTicket(
            id=uuid4().hex,
            request=request,
            enqueued_at=time.monotonic(),
            excluded_worker_ids=set(exclude_worker_ids or ()),
        )
        deadline = ticket.enqueued_at + timeout

        with self._condition:
            if not self._configured_route_exists(ticket):
                raise RuntimeError("no worker matches the configured id/region/tag route with a valid secret")
            if len(self._queue) >= self.max_queue_size:
                raise WorkerQueueFull("worker dispatch queue is full")
            self._queue.append(ticket)
            self.total_enqueued += 1
            self.peak_queue_depth = max(self.peak_queue_depth, len(self._queue))

            while True:
                available = self._available(ticket)
                if available:
                    selected = available[0]
                    if self._has_priority(ticket, selected):
                        state = self.pool.state[selected.id]
                        state.inflight += 1
                        self._queue.remove(ticket)
                        queued_ms = max(0, round((time.monotonic() - ticket.enqueued_at) * 1000))
                        self.total_dispatched += 1
                        self.total_wait_ms += queued_ms
                        self._condition.notify_all()
                        return WorkerLease(worker=selected, ticket_id=ticket.id, queued_ms=queued_ms)

                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    try:
                        self._queue.remove(ticket)
                    except ValueError:
                        pass
                    self.total_timed_out += 1
                    self._condition.notify_all()
                    raise WorkerQueueTimeout("timed out waiting for an eligible worker execution slot")
                self._condition.wait(timeout=min(remaining, 0.5))

    def release(self, lease: WorkerLease) -> None:
        with self._condition:
            state = self.pool.state[lease.worker.id]
            state.inflight = max(0, state.inflight - 1)
            self.total_released += 1
            self._condition.notify_all()

    def set_draining(self, worker_id: str, draining: bool) -> dict[str, Any]:
        spec = self.pool.get(worker_id)
        with self._condition:
            state = self.pool.state[spec.id]
            state.draining = bool(draining)
            self._condition.notify_all()
            return {
                "worker": spec.id,
                "draining": state.draining,
                "inflight": state.inflight,
                "max_concurrency": spec.max_concurrency,
                "note": "drain blocks new leases and does not interrupt inflight jobs",
            }

    def public_status(self) -> dict[str, Any]:
        with self._condition:
            average_wait_ms = round(self.total_wait_ms / self.total_dispatched) if self.total_dispatched else 0
            return {
                "strategy": "bounded weighted least-load with fair queue",
                "queue_depth": len(self._queue),
                "max_queue_size": self.max_queue_size,
                "queue_timeout_seconds": self.queue_timeout_seconds,
                "peak_queue_depth": self.peak_queue_depth,
                "total_enqueued": self.total_enqueued,
                "total_dispatched": self.total_dispatched,
                "total_timed_out": self.total_timed_out,
                "average_wait_ms": average_wait_ms,
                "workers": {
                    item.id: {
                        "inflight": self.pool.state[item.id].inflight,
                        "max_concurrency": item.max_concurrency,
                        "available_slots": max(0, item.max_concurrency - self.pool.state[item.id].inflight),
                        "draining": self.pool.state[item.id].draining,
                        "utilization_percent": round(
                            self.pool.state[item.id].inflight * 100 / item.max_concurrency, 1
                        ),
                    }
                    for item in self.pool.workers
                },
            }
