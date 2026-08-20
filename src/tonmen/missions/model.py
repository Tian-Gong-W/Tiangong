from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping
from uuid import uuid4


class StepState(str, Enum):
    PLANNED = "planned"
    WAITING_APPROVAL = "waiting_approval"


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
