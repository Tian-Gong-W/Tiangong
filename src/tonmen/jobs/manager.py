from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from tonmen.execution import ExecutionDenied, ExecutionOutcome, ToolExecutor
from tonmen.tools import ToolRequest


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    DENIED = "denied"


@dataclass(slots=True)
class Job:
    id: str
    request: ToolRequest
    status: JobStatus = JobStatus.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: datetime | None = None
    finished_at: datetime | None = None
    outcome: ExecutionOutcome | None = None
    error: str | None = None


class JobManager:
    """Synchronous Forge job lifecycle; async scheduling comes in a later milestone."""

    def __init__(self, executor: ToolExecutor) -> None:
        self.executor = executor
        self._jobs: dict[str, Job] = {}

    def submit(self, request: ToolRequest, *, approved: bool = False) -> Job:
        job = Job(id=uuid4().hex, request=request)
        self._jobs[job.id] = job
        job.status = JobStatus.RUNNING
        job.started_at = datetime.now(timezone.utc)
        try:
            job.outcome = self.executor.execute(request, approved=approved)
            job.status = JobStatus.SUCCEEDED if job.outcome.result.success else JobStatus.FAILED
        except ExecutionDenied as exc:
            job.status = JobStatus.DENIED
            job.error = str(exc)
        except Exception as exc:
            job.status = JobStatus.FAILED
            job.error = str(exc)
        finally:
            job.finished_at = datetime.now(timezone.utc)
        return job

    def get(self, job_id: str) -> Job:
        return self._jobs[job_id]
