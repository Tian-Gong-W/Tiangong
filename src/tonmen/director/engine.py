from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Mapping

from tonmen.agents.planner import MissionPlanner
from tonmen.core.runtime import TonmenRuntime
from tonmen.jobs import JobStatus
from tonmen.research import ActionRecord, ActionState, AdaptiveMissionState
from tonmen.tools import ToolRequest


@dataclass(frozen=True, slots=True)
class DirectorTickResult:
    state: AdaptiveMissionState
    outcome: str
    action_id: str | None
    explanation: str


class AdaptiveMissionDirector:
    """One-action-at-a-time adaptive research control plane.

    The Director may propose and schedule work, but it never bypasses Runtime
    authority. Every execution still travels through ToolRequest -> Policy ->
    Approval -> Executor. This preserves TONMEN's deny-by-default execution model
    while allowing the next action to be created after a Mission has started.
    """

    def __init__(self, runtime: TonmenRuntime, planner: MissionPlanner | None = None) -> None:
        self.runtime = runtime
        self.planner = planner or MissionPlanner(runtime)

    def start(self, target: str) -> AdaptiveMissionState:
        return self.planner.create_state(target)

    @staticmethod
    def _waiting_record(state: AdaptiveMissionState) -> ActionRecord | None:
        return next(
            (record for record in state.action_ledger if record.state is ActionState.WAITING_APPROVAL),
            None,
        )

    def tick(
        self,
        state: AdaptiveMissionState,
        *,
        approval_tokens: Mapping[str, str] | None = None,
    ) -> DirectorTickResult:
        if self.runtime.jobs is None:
            raise RuntimeError("adaptive Director requires an initialized JobManager")

        approval_tokens = approval_tokens or {}
        record = self._waiting_record(state)

        if record is None:
            decision = self.planner.decide_next(state)
            proposal = decision.best
            if proposal is None:
                state.converged = True
                return DirectorTickResult(
                    state=state,
                    outcome="converged",
                    action_id=None,
                    explanation=decision.explanation,
                )
            record = ActionRecord(proposal=proposal)
            state.action_ledger.append(record)
        else:
            proposal = record.proposal

        approval_token = approval_tokens.get(proposal.id)
        if proposal.requires_approval and not approval_token:
            record.state = ActionState.WAITING_APPROVAL
            return DirectorTickResult(
                state=state,
                outcome="approval_required",
                action_id=proposal.id,
                explanation="selected action remains pending until a matching Runtime approval token is supplied",
            )

        request = ToolRequest(
            tool=proposal.capability,
            target=proposal.target,
            parameters=proposal.parameters,
            context={
                "mission_id": state.mission_id,
                "action_id": proposal.id,
                "hypothesis_ids": list(proposal.hypothesis_ids),
                "planner_mode": "adaptive",
            },
        )
        job = self.runtime.jobs.submit(request, approval_token=approval_token)
        record.job_id = job.id
        record.finished_at = datetime.now(timezone.utc)

        if job.outcome is not None:
            evidence_id = job.outcome.evidence.id
            record.evidence_id = evidence_id
            if evidence_id not in state.evidence_ids:
                state.evidence_ids.append(evidence_id)

        if job.status is JobStatus.SUCCEEDED:
            record.state = ActionState.SUCCEEDED
            outcome = "executed"
        elif job.status is JobStatus.DENIED:
            record.state = ActionState.DENIED
            record.error = job.error
            outcome = "denied"
        else:
            record.state = ActionState.FAILED
            record.error = job.error or (job.outcome.result.summary if job.outcome is not None else "execution failed")
            outcome = "failed"

        return DirectorTickResult(
            state=state,
            outcome=outcome,
            action_id=proposal.id,
            explanation=(
                "action was selected from current mission state and executed through the existing governed Runtime path"
            ),
        )
