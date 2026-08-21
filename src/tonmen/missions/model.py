from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping
from uuid import uuid4

from tonmen.tools.base import CostEstimate


class StepState(str, Enum):
    PLANNED = "planned"
    WAITING_APPROVAL = "waiting_approval"


@dataclass(frozen=True, slots=True)
class ActionProposal:
    """A planner proposal. It never grants execution authority by itself."""

    id: str
    capability: str
    target: str | None
    hypothesis_ids: tuple[str, ...]
    input_artifact_ids: tuple[str, ...]
    parameters: Mapping[str, Any]
    expected_information_gain: float
    relevance: float
    estimated_cost: CostEstimate
    risk: int
    replayable: bool
    requires_approval: bool
    evidence_requirements: tuple[str, ...]
    rationale: str

    def __post_init__(self) -> None:
        if self.expected_information_gain < 0:
            raise ValueError("expected_information_gain cannot be negative")
        if not 0.0 <= self.relevance <= 1.0:
            raise ValueError("relevance must be between 0 and 1")

    @property
    def utility_score(self) -> float:
        return (self.expected_information_gain * self.relevance) / self.estimated_cost.effective_units

    @classmethod
    def create(
        cls,
        *,
        capability: str,
        target: str | None,
        parameters: Mapping[str, Any],
        hypothesis_ids: tuple[str, ...] = (),
        input_artifact_ids: tuple[str, ...] = (),
        expected_information_gain: float,
        relevance: float,
        estimated_cost: CostEstimate,
        risk: int,
        replayable: bool,
        requires_approval: bool,
        evidence_requirements: tuple[str, ...] = (),
        rationale: str,
    ) -> "ActionProposal":
        return cls(
            id=uuid4().hex,
            capability=capability,
            target=target,
            hypothesis_ids=hypothesis_ids,
            input_artifact_ids=input_artifact_ids,
            parameters=dict(parameters),
            expected_information_gain=expected_information_gain,
            relevance=relevance,
            estimated_cost=estimated_cost,
            risk=risk,
            replayable=replayable,
            requires_approval=requires_approval,
            evidence_requirements=evidence_requirements,
            rationale=rationale,
        )


@dataclass(frozen=True, slots=True)
class MissionStep:
    id: str
    tool: str
    target: str
    parameters: Mapping[str, Any]
    risk: int
    requires_approval: bool
    state: StepState
    rationale: str

    @classmethod
    def create(
        cls,
        *,
        tool: str,
        target: str,
        parameters: Mapping[str, Any],
        risk: int,
        requires_approval: bool,
        rationale: str,
    ) -> "MissionStep":
        return cls(
            id=uuid4().hex,
            tool=tool,
            target=target,
            parameters=dict(parameters),
            risk=risk,
            requires_approval=requires_approval,
            state=StepState.WAITING_APPROVAL if requires_approval else StepState.PLANNED,
            rationale=rationale,
        )


@dataclass(frozen=True, slots=True)
class MissionPlan:
    id: str
    target: str
    steps: tuple[MissionStep, ...]
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        target: str,
        steps: list[MissionStep],
        *,
        metadata: Mapping[str, Any] | None = None,
    ) -> "MissionPlan":
        return cls(id=uuid4().hex, target=target, steps=tuple(steps), metadata=dict(metadata or {}))
