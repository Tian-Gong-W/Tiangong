from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from tonmen.evidence import EvidenceGraph, EvidenceRecord
from tonmen.missions.model import MissionPlan
from tonmen.observations import Observation


class MissionRunState(str, Enum):
    CREATED = "created"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    DENIED = "denied"


class StepExecutionState(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    SUCCEEDED = "succeeded"
    SKIPPED = "skipped"
    FAILED = "failed"
    DENIED = "denied"


@dataclass(slots=True)
class StepExecution:
    step_id: str
    tool: str
    target: str
    state: StepExecutionState = StepExecutionState.PENDING
    job_id: str | None = None
    evidence_id: str | None = None
    observation_id: str | None = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class MissionRun:
    id: str
    plan_id: str
    target: str
    state: MissionRunState
    steps: list[StepExecution]
    observations: list[Observation]
    evidence: list[EvidenceRecord]
    graph: EvidenceGraph
    started_at: datetime
    finished_at: datetime | None = None

    @classmethod
    def create(cls, plan: MissionPlan) -> "MissionRun":
        return cls(
            id=uuid4().hex,
            plan_id=plan.id,
            target=plan.target,
            state=MissionRunState.CREATED,
            steps=[StepExecution(step_id=step.id, tool=step.tool, target=step.target) for step in plan.steps],
            observations=[],
            evidence=[],
            graph=EvidenceGraph(),
            started_at=datetime.now(timezone.utc),
        )

    def finish(self, state: MissionRunState) -> None:
        self.state = state
        if state in {MissionRunState.SUCCEEDED, MissionRunState.FAILED, MissionRunState.DENIED}:
            self.finished_at = datetime.now(timezone.utc)
