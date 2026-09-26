from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .run import StepExecution, StepExecutionState


_TERMINAL_ACTION_STATES = {
    StepExecutionState.SUCCEEDED,
    StepExecutionState.DEGRADED,
    StepExecutionState.SKIPPED,
    StepExecutionState.FAILED,
    StepExecutionState.DENIED,
}


@dataclass(slots=True)
class ActionLedger:
    """Runtime action history backed by the persisted MissionRun execution list.

    TONMEN historically persisted actions under ``MissionRun.steps``.  The ledger
    deliberately wraps that list instead of introducing a second persistence
    structure: old Chronicle records remain readable while new orchestration can
    reason in terms of actions rather than a frozen plan.

    ``legacy_slots`` marks the immutable prefix created from MissionPlan.steps.
    Everything appended after that prefix is late-bound runtime work.
    """

    entries: list[StepExecution]
    legacy_slots: int = 0

    def __post_init__(self) -> None:
        if self.legacy_slots < 0:
            raise ValueError("legacy_slots cannot be negative")
        if self.legacy_slots > len(self.entries):
            raise ValueError("legacy_slots cannot exceed persisted action count")

    def __iter__(self) -> Iterable[StepExecution]:
        return iter(self.entries)

    def __len__(self) -> int:
        return len(self.entries)

    @property
    def legacy(self) -> tuple[StepExecution, ...]:
        return tuple(self.entries[: self.legacy_slots])

    @property
    def dynamic(self) -> tuple[StepExecution, ...]:
        return tuple(self.entries[self.legacy_slots :])

    def get(self, action_id: str) -> StepExecution | None:
        return next((entry for entry in self.entries if entry.id == action_id), None)

    def dynamic_for_proposal(self, proposal_id: str) -> StepExecution | None:
        return next(
            (
                entry
                for entry in self.dynamic
                if str(entry.metadata.get("proposal_id") or "") == proposal_id
            ),
            None,
        )

    def waiting_for_approval(self) -> StepExecution | None:
        return next(
            (entry for entry in self.entries if entry.state is StepExecutionState.WAITING_APPROVAL),
            None,
        )

    def first_pending_legacy(self) -> StepExecution | None:
        return next(
            (entry for entry in self.legacy if entry.state is StepExecutionState.PENDING),
            None,
        )

    def append_dynamic(
        self,
        *,
        action_id: str,
        tool: str,
        target: str,
        proposal_id: str,
        state: StepExecutionState = StepExecutionState.PENDING,
        metadata: dict | None = None,
        error: str | None = None,
    ) -> StepExecution:
        if self.get(action_id) is not None:
            raise ValueError(f"action already exists: {action_id}")
        entry = StepExecution(
            step_id=action_id,
            tool=tool,
            target=target,
            state=state,
            error=error,
            metadata={"dynamic": True, "proposal_id": proposal_id, **dict(metadata or {})},
        )
        self.entries.append(entry)
        return entry

    def remove_dynamic(self, entry: StepExecution) -> None:
        if entry in self.legacy:
            raise ValueError("legacy action slots cannot be removed")
        self.entries.remove(entry)

    def state_signature(self) -> tuple[tuple[str, str], ...]:
        return tuple((entry.id, entry.state.value) for entry in self.entries)

    def unfinished(self) -> tuple[StepExecution, ...]:
        return tuple(entry for entry in self.entries if entry.state not in _TERMINAL_ACTION_STATES)
