from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from tonmen.missions import MissionRun
from tonmen.reasoning import ReasoningDecision


class LoopStopReason(str, Enum):
    COMPLETE = "complete"
    APPROVAL_REQUIRED = "approval_required"
    REVIEW_REQUIRED = "review_required"
    TERMINAL = "terminal"
    EXECUTION_BUDGET = "execution_budget"
    MAX_ITERATIONS = "max_iterations"
    REPEATED_DECISION = "repeated_decision"
    TIME_BUDGET = "time_budget"


@dataclass(frozen=True, slots=True)
class MissionLoopPolicy:
    max_iterations: int = 8
    max_executions: int = 3
    max_repeat_decisions: int = 2
    max_duration_seconds: int = 1200
    assessment_rounds: int = 8
    subagents_per_round: int = 4

    def __post_init__(self) -> None:
        if not 1 <= self.max_iterations <= 64:
            raise ValueError("max_iterations must be between 1 and 64")
        if not 1 <= self.max_executions <= 16:
            raise ValueError("max_executions must be between 1 and 16")
        if not 1 <= self.max_repeat_decisions <= 8:
            raise ValueError("max_repeat_decisions must be between 1 and 8")
        if not 1 <= self.max_duration_seconds <= 10800:
            raise ValueError("max_duration_seconds must be between 1 and 10800")
        if not 7 <= self.assessment_rounds <= 10:
            raise ValueError("assessment_rounds must be between 7 and 10")
        if not 3 <= self.subagents_per_round <= 5:
            raise ValueError("subagents_per_round must be between 3 and 5")


@dataclass(frozen=True, slots=True)
class MissionLoopResult:
    run: MissionRun
    stop_reason: LoopStopReason
    iterations: int
    executions: int
    session_id: str
    last_decision: ReasoningDecision | None = None
