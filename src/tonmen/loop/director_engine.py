from __future__ import annotations

from time import monotonic
from typing import Mapping
from uuid import uuid4

from tonmen.evidence import GraphNode
from tonmen.missions import (
    ActionLedger,
    MissionPlan,
    MissionRun,
    MissionRunState,
    StepExecution,
    StepExecutionState,
    iter_plan_executions,
)
from tonmen.reasoning import ActionProposal, MissionDirector, ReasoningAction, ReasoningDecision

from .engine import MissionLoop as _LegacyMissionLoop
from .model import LoopStopReason, MissionLoopResult


class MissionLoop(_LegacyMissionLoop):
    """Director-first observe → reason → act loop.

    MissionPlan remains a compatibility projection for older callers. Runtime work
    is tracked through ActionLedger, while MissionDirector owns each next-action
    decision from the current evidence state.
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        # The runtime is essential: without it the Director intentionally degrades
        # to the legacy compatibility facade and cannot rank Registry capabilities.
        self.director = MissionDirector(self.runtime)
        self.reasoner = self.director.reasoner

    @staticmethod
    def _ledger(plan: MissionPlan, run: MissionRun) -> ActionLedger:
        return ActionLedger(run.steps, legacy_slots=len(plan.steps))

    @staticmethod
    def _legacy_plan_complete(plan: MissionPlan, run: MissionRun) -> bool:
        return all(
            execution.state
            in {
                StepExecutionState.SUCCEEDED,
                StepExecutionState.DEGRADED,
                StepExecutionState.SKIPPED,
            }
            for _, execution in iter_plan_executions(plan, run)
        )

    @staticmethod
    def _close_legacy_plan(plan: MissionPlan, run: MissionRun, *, decision_id: str) -> None:
        for _, execution in iter_plan_executions(plan, run):
            if execution.state not in {StepExecutionState.PENDING, StepExecutionState.WAITING_APPROVAL}:
                continue
            execution.state = StepExecutionState.SKIPPED
            execution.error = None
            execution.metadata["superseded_by_director"] = decision_id

    @staticmethod
    def _next_step_would_execute(
        plan: MissionPlan,
        run: MissionRun,
        approval_tokens: Mapping[str, str],
    ) -> bool:
        for planned, execution in iter_plan_executions(plan, run):
            if execution.state in {
                StepExecutionState.SUCCEEDED,
                StepExecutionState.DEGRADED,
                StepExecutionState.SKIPPED,
            }:
                continue
            if planned.requires_approval and not approval_tokens.get(planned.id):
                return False
            return True
        return False

    @classmethod
    def _dynamic_execution(cls, plan: MissionPlan, run: MissionRun, proposal_id: str) -> StepExecution | None:
        return cls._ledger(plan, run).dynamic_for_proposal(proposal_id)

    def _materialize_dynamic_wait(
        self,
        plan: MissionPlan,
        run: MissionRun,
        proposal: ActionProposal,
    ) -> StepExecution:
        ledger = self._ledger(plan, run)
        action_id = f"dynamic:{proposal.id}"
        execution = ledger.dynamic_for_proposal(proposal.id)
        if execution is None:
            execution = ledger.append_dynamic(
                action_id=action_id,
                tool=proposal.tool,
                target=proposal.target,
                proposal_id=proposal.id,
                state=StepExecutionState.WAITING_APPROVAL,
                error="explicit approval grant required",
                metadata={
                    "hypothesis_id": proposal.hypothesis_id,
                    "expected_info_gain": proposal.expected_info_gain,
                    "risk": proposal.risk,
                    "rationale": proposal.rationale,
                    "requires_approval": proposal.requires_approval,
                },
            )
        else:
            execution.state = StepExecutionState.WAITING_APPROVAL
            execution.error = "explicit approval grant required"

        if action_id not in run.graph.nodes:
            run.graph.add_node(
                GraphNode(
                    id=action_id,
                    kind="step.dynamic",
                    label=f"{proposal.tool}:{proposal.target}",
                    metadata={
                        "risk": proposal.risk,
                        "requires_approval": proposal.requires_approval,
                        "proposal_id": proposal.id,
                        "dynamic": True,
                    },
                )
            )
            run.graph.link(run.id, "contains", action_id)
            if proposal.id in run.graph.nodes:
                run.graph.link(proposal.id, "realized_as", action_id)

        proposal_node = run.graph.nodes.get(proposal.id)
        if proposal_node is not None:
            run.graph.nodes[proposal.id] = GraphNode(
                id=proposal_node.id,
                kind=proposal_node.kind,
                label=proposal_node.label,
                metadata={**dict(proposal_node.metadata), "status": "waiting_approval", "action_id": action_id},
            )

        run.state = MissionRunState.WAITING_APPROVAL
        return execution

    def _schedule_one_proposal(
        self,
        plan: MissionPlan,
        run: MissionRun,
        decision: ReasoningDecision,
        *,
        approval_tokens: Mapping[str, str],
    ) -> int:
        """Execute at most one candidate ActionProposal for this reasoning turn."""
        proposal = decision.new_proposals[0]
        action_id = f"dynamic:{proposal.id}"
        token = approval_tokens.get(action_id)
        ledger = self._ledger(plan, run)
        existing = ledger.dynamic_for_proposal(proposal.id)

        if existing is not None and existing.state is StepExecutionState.WAITING_APPROVAL and not token:
            run.state = MissionRunState.WAITING_APPROVAL
            return 0

        if existing is not None and existing.state is StepExecutionState.WAITING_APPROVAL and token:
            # Coordinator still materializes the executing record. Remove only the
            # parked dynamic placeholder; legacy slots are immutable ledger prefix.
            ledger.remove_dynamic(existing)
            run.state = MissionRunState.RUNNING

        accepted = self.coordinator.execute_proposal(run, proposal, approval_token=token)
        if accepted and run.state is MissionRunState.WAITING_APPROVAL:
            self._materialize_dynamic_wait(plan, run, proposal)
            return 0
        return 1 if accepted else 0

    def _advance_legacy_once(
        self,
        plan: MissionPlan,
        run: MissionRun,
        *,
        approval_tokens: Mapping[str, str],
    ) -> None:
        """Execute one compatibility slot without letting plan exhaustion end Mission."""
        original_emit = self.coordinator._emit

        def guarded_emit(event_type: str, mission_run: MissionRun, **data: object) -> None:
            if event_type == "mission.completed":
                return
            original_emit(event_type, mission_run, **data)

        self.coordinator._emit = guarded_emit
        try:
            self.coordinator.advance_once(plan, run, approval_tokens=approval_tokens)
        finally:
            self.coordinator._emit = original_emit

        if run.state is MissionRunState.SUCCEEDED and self._legacy_plan_complete(plan, run):
            run.state = MissionRunState.RUNNING
            run.finished_at = None

    def _drive(
        self,
        plan: MissionPlan,
        run: MissionRun,
        *,
        approval_tokens: Mapping[str, str],
    ) -> MissionLoopResult:
        session_id = uuid4().hex
        self.coordinator._ensure_graph(plan, run)
        self._record_session(run, session_id)
        self._checkpoint(plan, run)

        started = monotonic()
        executions = 0
        repeated: dict[tuple[object, ...], int] = {}
        last_decision: ReasoningDecision | None = None

        for iteration in range(1, self.policy.max_iterations + 1):
            if monotonic() - started >= self.policy.max_duration_seconds:
                return self._result(
                    plan,
                    run,
                    session_id=session_id,
                    reason=LoopStopReason.TIME_BUDGET,
                    iterations=iteration - 1,
                    executions=executions,
                    decision=last_decision,
                )

            decision = self.director.decide_next(plan, run, approval_tokens=approval_tokens)
            last_decision = decision
            self.coordinator.record_reasoning(run, decision)
            self._emit(
                "reasoning.decided",
                run,
                decision_id=decision.id,
                action=decision.action.value,
                summary=decision.summary,
                basis_fact_ids=list(decision.basis_fact_ids),
                next_step_id=decision.next_step_id,
                requires_human=decision.requires_human,
                proposal_count=len(decision.new_proposals),
                authority="mission_director",
            )

            if decision.hypotheses:
                self._apply_hypothesis_updates(run, decision)
            if decision.new_proposals or decision.hypotheses:
                self._record_hypotheses_and_proposals(run, decision)

            key = self._decision_key(decision)
            repeated[key] = repeated.get(key, 0) + 1
            evidence_before = len(run.evidence)
            states_before = self._ledger(plan, run).state_signature()
            evidence_added = 0

            if decision.action is ReasoningAction.NO_ACTION:
                self._record_iteration(
                    run,
                    session_id=session_id,
                    iteration=iteration,
                    executions=executions,
                    decision=decision,
                    evidence_added=0,
                )
                return self._result(
                    plan,
                    run,
                    session_id=session_id,
                    reason=LoopStopReason.NO_EXECUTABLE_ACTION,
                    iterations=iteration,
                    executions=executions,
                    decision=decision,
                )

            if decision.action is ReasoningAction.PROPOSE and decision.new_proposals:
                if executions >= self.policy.max_executions:
                    return self._result(
                        plan,
                        run,
                        session_id=session_id,
                        reason=LoopStopReason.EXECUTION_BUDGET,
                        iterations=iteration - 1,
                        executions=executions,
                        decision=decision,
                    )
                selected = decision.new_proposals[0]
                scheduled = self._schedule_one_proposal(
                    plan,
                    run,
                    decision,
                    approval_tokens=approval_tokens,
                )
                executions += scheduled
                evidence_added = len(run.evidence) - evidence_before
                self._emit(
                    "proposal.scheduled",
                    run,
                    decision_id=decision.id,
                    proposal_ids=[selected.id],
                    candidate_count=len(decision.new_proposals),
                    scheduled=scheduled,
                )
                if run.state is MissionRunState.WAITING_APPROVAL:
                    self._record_iteration(
                        run,
                        session_id=session_id,
                        iteration=iteration,
                        executions=executions,
                        decision=decision,
                        evidence_added=evidence_added,
                    )
                    return self._result(
                        plan,
                        run,
                        session_id=session_id,
                        reason=LoopStopReason.APPROVAL_REQUIRED,
                        iterations=iteration,
                        executions=executions,
                        decision=decision,
                    )

            elif decision.action is ReasoningAction.SKIP:
                if self.coordinator.apply_reasoning_decision(plan, run, decision):
                    self._emit("step.skipped", run, step_id=decision.next_step_id, reason=decision.summary)

            elif decision.action is ReasoningAction.REQUEST_APPROVAL:
                if decision.next_step_id:
                    for planned, execution in iter_plan_executions(plan, run):
                        if planned.id != decision.next_step_id:
                            continue
                        execution.state = StepExecutionState.WAITING_APPROVAL
                        execution.error = "explicit approval grant required"
                        run.state = MissionRunState.WAITING_APPROVAL
                        self._emit(
                            "approval.required",
                            run,
                            step_id=planned.id,
                            tool=planned.tool,
                            step_target=planned.target,
                            risk=planned.risk,
                            authority="mission_director",
                        )
                        break
                self._record_iteration(
                    run,
                    session_id=session_id,
                    iteration=iteration,
                    executions=executions,
                    decision=decision,
                    evidence_added=0,
                )
                return self._result(
                    plan,
                    run,
                    session_id=session_id,
                    reason=LoopStopReason.APPROVAL_REQUIRED,
                    iterations=iteration,
                    executions=executions,
                    decision=decision,
                )

            elif decision.action is ReasoningAction.REVIEW:
                if self._legacy_plan_complete(plan, run) and run.state is MissionRunState.RUNNING:
                    run.finish(MissionRunState.SUCCEEDED)
                self._record_iteration(
                    run,
                    session_id=session_id,
                    iteration=iteration,
                    executions=executions,
                    decision=decision,
                    evidence_added=0,
                )
                return self._result(
                    plan,
                    run,
                    session_id=session_id,
                    reason=LoopStopReason.REVIEW_REQUIRED,
                    iterations=iteration,
                    executions=executions,
                    decision=decision,
                )

            elif run.state in {MissionRunState.FAILED, MissionRunState.DENIED} or decision.action is ReasoningAction.STOP:
                self._record_iteration(
                    run,
                    session_id=session_id,
                    iteration=iteration,
                    executions=executions,
                    decision=decision,
                    evidence_added=0,
                )
                return self._result(
                    plan,
                    run,
                    session_id=session_id,
                    reason=LoopStopReason.TERMINAL,
                    iterations=iteration,
                    executions=executions,
                    decision=decision,
                )

            elif decision.action is ReasoningAction.COMPLETE:
                if run.state not in {MissionRunState.SUCCEEDED, MissionRunState.FAILED, MissionRunState.DENIED}:
                    self._close_legacy_plan(plan, run, decision_id=decision.id)
                    run.finish(MissionRunState.SUCCEEDED)
                    self._emit("mission.completed", run, authority="mission_director")

            elif decision.action is ReasoningAction.CONTINUE:
                if executions >= self.policy.max_executions and self._next_step_would_execute(plan, run, approval_tokens):
                    return self._result(
                        plan,
                        run,
                        session_id=session_id,
                        reason=LoopStopReason.EXECUTION_BUDGET,
                        iterations=iteration - 1,
                        executions=executions,
                        decision=decision,
                    )

                ledger = self._ledger(plan, run)
                jobs_before = {entry.id: entry.job_id for entry in ledger}
                self._advance_legacy_once(plan, run, approval_tokens=approval_tokens)
                executions += sum(
                    1
                    for entry in self._ledger(plan, run)
                    if entry.job_id is not None and jobs_before.get(entry.id) != entry.job_id
                )
                evidence_added = len(run.evidence) - evidence_before

            max_gain = max((proposal.expected_info_gain for proposal in decision.new_proposals), default=0.0)
            report = self.convergence.observe(run, max_expected_info_gain=max_gain)
            self._emit(
                "convergence.observed",
                run,
                converged=report.converged,
                reason=report.reason,
                open_hypotheses=report.open_hypotheses,
                recent_fact_gain=report.recent_fact_gain,
                recent_proposal_gain=report.recent_proposal_gain,
                max_expected_info_gain=report.max_expected_info_gain,
            )

            self._record_iteration(
                run,
                session_id=session_id,
                iteration=iteration,
                executions=executions,
                decision=decision,
                evidence_added=evidence_added,
            )
            self._record_council_round(plan, run, session_id=session_id, decision=decision, phase="live")
            self._checkpoint(plan, run)

            if report.converged and decision.action is not ReasoningAction.COMPLETE:
                return self._result(
                    plan,
                    run,
                    session_id=session_id,
                    reason=LoopStopReason.CONVERGED,
                    iterations=iteration,
                    executions=executions,
                    decision=decision,
                )

            states_after = self._ledger(plan, run).state_signature()
            no_progress = evidence_added == 0 and states_before == states_after
            if repeated[key] > self.policy.max_repeat_decisions and no_progress:
                return self._result(
                    plan,
                    run,
                    session_id=session_id,
                    reason=LoopStopReason.REPEATED_DECISION,
                    iterations=iteration,
                    executions=executions,
                    decision=decision,
                )

            if run.state is MissionRunState.WAITING_APPROVAL:
                return self._result(
                    plan,
                    run,
                    session_id=session_id,
                    reason=LoopStopReason.APPROVAL_REQUIRED,
                    iterations=iteration,
                    executions=executions,
                    decision=decision,
                )

            if run.state in {MissionRunState.FAILED, MissionRunState.DENIED}:
                return self._result(
                    plan,
                    run,
                    session_id=session_id,
                    reason=LoopStopReason.TERMINAL,
                    iterations=iteration,
                    executions=executions,
                    decision=decision,
                )

            if decision.action is ReasoningAction.COMPLETE:
                return self._result(
                    plan,
                    run,
                    session_id=session_id,
                    reason=LoopStopReason.COMPLETE,
                    iterations=iteration,
                    executions=executions,
                    decision=decision,
                )

        return self._result(
            plan,
            run,
            session_id=session_id,
            reason=LoopStopReason.MAX_ITERATIONS,
            iterations=self.policy.max_iterations,
            executions=executions,
            decision=last_decision,
        )
