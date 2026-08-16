from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from uuid import uuid4


class ReasoningAction(str, Enum):
    CONTINUE = "continue"
    REQUEST_APPROVAL = "request_approval"
    SKIP = "skip"
    REVIEW = "review"
    COMPLETE = "complete"
    STOP = "stop"


@dataclass(frozen=True, slots=True)
class ReasoningDecision:
    id: str
    action: ReasoningAction
    summary: str
    basis_fact_ids: tuple[str, ...] = ()
    next_step_id: str | None = None
    requires_human: bool = False

    @classmethod
    def create(
        cls,
        *,
        action: ReasoningAction,
        summary: str,
        basis_fact_ids: tuple[str, ...] = (),
        next_step_id: str | None = None,
        requires_human: bool = False,
    ) -> "ReasoningDecision":
        return cls(
            id=uuid4().hex,
            action=action,
            summary=summary,
            basis_fact_ids=tuple(basis_fact_ids),
            next_step_id=next_step_id,
            requires_human=requires_human,
        )
