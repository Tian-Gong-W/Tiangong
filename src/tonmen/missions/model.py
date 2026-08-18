from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable, Mapping
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

    @classmethod
    def create(cls, target: str, steps: list[MissionStep]) -> "MissionPlan":
        return cls(id=uuid4().hex, target=target, steps=tuple(steps))

    def extend(self, steps: Iterable[MissionStep]) -> "MissionPlan":
        """Return a revision that preserves plan identity and appends governed steps.

        Plans stay immutable so every Chronicle checkpoint receives an explicit revision.
        A revision may only append unique step identities; existing history cannot be
        silently rewritten or reordered.
        """
        additions = tuple(steps)
        if not additions:
            return self
        existing = {step.id for step in self.steps}
        incoming = [step.id for step in additions]
        if len(set(incoming)) != len(incoming) or existing.intersection(incoming):
            raise ValueError("plan revision contains a duplicate step id")
        return MissionPlan(id=self.id, target=self.target, steps=self.steps + additions)
