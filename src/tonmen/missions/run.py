from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from tonmen.evidence import EvidenceGraph, EvidenceRecord, GraphNode
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
    DEGRADED = "degraded"
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

    @property
    def id(self) -> str:
        """Stable action identity used by approval/resume code.

        Frozen plan executions and late-bound dynamic actions share the same runtime
        lifecycle even though the compatibility field is still named ``step_id``.
        """
        return self.step_id


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
        run_id = uuid4().hex
        graph = EvidenceGraph()
        graph.add_node(GraphNode(id=run_id, kind="mission", label=f"mission:{plan.target}", metadata={"plan_id": plan.id}))

        for step in plan.steps:
            graph.add_node(
                GraphNode(
                    id=step.id,
                    kind="step",
                    label=f"{step.tool}:{step.target}",
                    metadata={"risk": step.risk, "requires_approval": step.requires_approval},
                )
            )
            graph.link(run_id, "contains", step.id)

        resolved = plan.metadata.get("resolved_assets") if isinstance(plan.metadata, dict) else None
        if isinstance(resolved, dict):
            for index, asset in enumerate(resolved.get("assets", [])):
                if not isinstance(asset, dict) or not asset.get("address"):
                    continue
                node_id = f"asset:{run_id}:{index}"
                graph.add_node(
                    GraphNode(
                        id=node_id,
                        kind="asset.resolved",
                        label=str(asset.get("address")),
                        metadata={
                            "address": str(asset.get("address")),
                            "family": str(asset.get("family") or "unknown"),
                            "source": str(asset.get("source") or "dns"),
                            "authorized": bool(asset.get("authorized")),
                            "scope_status": str(asset.get("scope_status") or "needs_scope"),
                            "execution_authority": False,
                        },
                    )
                )
                graph.link(run_id, "resolved_to", node_id)

        coverage = plan.metadata.get("coverage_plan") if isinstance(plan.metadata, dict) else None
        if isinstance(coverage, dict):
            coverage_id = f"coverage:{run_id}"
            graph.add_node(
                GraphNode(
                    id=coverage_id,
                    kind="coverage.plan",
                    label="scope-aware resolved asset coverage",
                    metadata=dict(coverage),
                )
            )
            graph.link(run_id, "governed_by", coverage_id)

        return cls(
            id=run_id,
            plan_id=plan.id,
            target=plan.target,
            state=MissionRunState.CREATED,
            steps=[StepExecution(step_id=step.id, tool=step.tool, target=step.target) for step in plan.steps],
            observations=[],
            evidence=[],
            graph=graph,
            started_at=datetime.now(timezone.utc),
        )

    def finish(self, state: MissionRunState) -> None:
        self.state = state
        if state in {MissionRunState.SUCCEEDED, MissionRunState.FAILED, MissionRunState.DENIED}:
            self.finished_at = datetime.now(timezone.utc)


def iter_plan_executions(plan: MissionPlan, run: MissionRun):
    """Pair frozen plan steps with their original execution slots.

    Dynamic actions are appended to ``run.steps`` after mission start, so callers
    that reason about the compatibility ``MissionPlan`` must ignore those later
    entries instead of using ``zip(..., strict=True)`` across the full run.
    """
    if len(run.steps) < len(plan.steps):
        raise ValueError("mission run is missing execution slots for the frozen plan")
    return zip(plan.steps, run.steps[: len(plan.steps)], strict=True)
