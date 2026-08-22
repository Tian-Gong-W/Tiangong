from __future__ import annotations

from time import monotonic
from typing import Mapping
from uuid import uuid4

from tonmen.missions import MissionPlan, MissionRun, MissionRunState, StepExecutionState, iter_plan_executions
from tonmen.reasoning import MissionDirector, ReasoningAction, ReasoningDecision

from .engine import MissionLoop as _LegacyMissionLoop
from .model import LoopStopReason, MissionLoopResult


class MissionLoop(_LegacyMissionLoop):
    """Director-first loop with frozen-plan compatibility only as an action source."""

    def __init__(self, runtime, *args, **kwargs) -> None:
        super().__init__(runtime, *args, **kwargs)
        self.director = MissionDirector(runtime)
        self.reasoner = self.director.reasoner

    @staticmethod
    def _legacy_plan_complete(plan: MissionPlan, run: MissionRun) -> bool:
        return all(
            execution.state in {StepExecutionState.SUCCEEDED, StepExecutionState.DEGRADED, StepExecutionState.SKIPPED}
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
    def _next_step_would_execute(plan: MissionPlan, run: MissionRun, approval_tokens: Mapping[str, str]) -> bool:
        for planned, execution in iter_plan_executions(plan, run):
            if execution.state in {StepExecutionState.SUCCEEDED, StepExecutionState.DEGRADED, StepExecutionState.SKIPPED}:
                continue
            if planned.requires_approval and not approval_tokens.get(planned.id):
                return False
            return True
        return False

    def _advance_selected_legacy_once(
        self,
        plan: MissionPlan,
        run: MissionRun,
        *,
        approval_tokens: Mapping[str, str],
        step_id: str | None,
    ) -> None:
        """Execute exactly the Director-selected compatibility action.

        The legacy coordinator still walks ``MissionPlan.steps``. During migration,
        hide unrelated pending slots for one call rather than giving the frozen
        plan authority over ordering. Low-risk discovery failures with evidence are
        converted to degraded observations so the Director can re-plan.
        """
        selected = None
        if step_id is not None:
            for planned, execution in iter_plan_executions(plan, run):
                if planned.id == step_id:
                    selected = (planned, execution)
                    break
            if selected is None:
                raise ValueError(f"requested mission step does not exist: {step_id}")

        masked = []
        if selected is not None:
            selected_planned, selected_execution = selected
            for planned, execution in iter_plan_executions(plan, run):
                if planned.id == selected_planned.id:
                    continue
                if execution.state is StepExecutionState.PENDING:
                    masked.append((execution, execution.state))
                    execution.state = StepExecutionState.SKIPPED
        else:
            selected_planned = selected_execution = None

        original_emit = self.coordinator._emit
        selected_is_discovery = bool(selected_planned and selected_planned.risk <= 1)

        def guarded_emit(event_type: str, mission_run: MissionRun, **data: object) -> None:
            if event_type == "mission.completed":
                return
            if selected_is_discovery and event_type in {"step.failed", "mission.failed"}:
                return
            original_emit(event_type, mission_run, **data)

        self.coordinator._emit = guarded_emit
        try:
            self.coordinator.advance_once(plan, run, approval_tokens=approval_tokens)
        finally:
            self.coordinator._emit = original_emit
            for execution, old_state in masked:
                execution.state = old_state

        if (
            selected_is_discovery
            and selected_execution is not None
            and selected_execution.state is StepExecutionState.FAILED
            and selected_execution.evidence_id
        ):
            selected_execution.state = StepExecutionState.DEGRADED
            selected_execution.metadata["degraded_reason"] = "discovery_error"
            run.state = MissionRunState.RUNNING
            run.finished_at = None
            self._emit(
                "step.degraded",
                run,
                step_id=selected_planned.id,
                tool=selected_planned.tool,
                error=selected_execution.error,
                reason="discovery_error",
                evidence_id=selected_execution.evidence_id,
                authority="mission_director",
            )

        # Legacy plan exhaustion (or temporary masking) must never decide Mission
        # convergence. Control always returns to the Director.
        if run.state is MissionRunState.SUCCEEDED:
            run.state = MissionRunState.RUNNING
            run.finished_at = None

    def _degrade_dynamic_discovery_failures(self, run: MissionRun, *, start_index: int) -> None:
        for execution in run.steps[start_index:]:
            if not execution.metadata.get("dynamic"):
                continue
            if execution.state is not StepExecutionState.FAILED or not execution.evidence_id:
                continue
            if int(execution.metadata.get("risk", 99)) > 1:
                continue
            execution.state = StepExecutionState.DEGRADED
            execution.metadata["degraded_reason"] = "discovery_error"
            run.state = MissionRunState.RUNNING
            self._emit(
                "proposal.degraded",
                run,
                proposal_id=execution.metadata.get("proposal_id"),
                step_id=execution.step_id,
                tool=execution.tool,
                error=execution.error,
                reason="discovery_error",
                evidence_id=execution.evidence_id,
                authority="mission_director",
            )

    def _finish_result(
        self,
        plan: MissionPlan,
        run: MissionRun,
        *,
        session_id: str,
        reason: LoopStopReason,
        iteration: int,
        executions: int,
        decision: ReasoningDecision,
        evidence_added: int = 0,
    ) -> MissionLoopResult:
        self._record_iteration(
            run,
            session_id=session_id,
            iteration=iteration,
            executions=executions,
            decision=decision,
            evidence_added=evidence_added,
        )
        self._checkpoint(plan, run)
        return self._result(
            plan,
            run,
            session_id=session_id,
            reason=reason,
            iterations=iteration,
            executions=executions,
            decision=decision,
        )

    def _drive(self, plan: MissionPlan, run: MissionRun, *, approval_tokens: Mapping[str, str]) -> MissionLoopResult:
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
                    plan, run, session_id=session_id, reason=LoopStopReason.TIME_BUDGET,
                    iterations=iteration - 1, executions=executions, decision=last_decision,
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
            states_before = tuple(step.state for step in run.steps)
            evidence_added = 0

            if decision.action is ReasoningAction.PROPOSE and decision.new_proposals:
                if executions >= self.policy.max_executions:
                    return self._result(
                        plan, run, session_id=session_id, reason=LoopStopReason.EXECUTION_BUDGET,
                        iterations=iteration - 1, executions=executions, decision=decision,
                    )
                dynamic_start = len(run.steps)
                scheduled = self._schedule_proposals(run, decision, executions=executions)
                self._degrade_dynamic_discovery_failures(run, start_index=dynamic_start)
                executions += scheduled
                evidence_added = len(run.evidence) - evidence_before
                self._emit(
                    "proposal.scheduled",
                    run,
                    decision_id=decision.id,
                    proposal_ids=[proposal.id for proposal in decision.new_proposals],
                    scheduled=scheduled,
                )
                if run.state is MissionRunState.WAITING_APPROVAL:
                    return self._finish_result(
                        plan, run, session_id=session_id, reason=LoopStopReason.APPROVAL_REQUIRED,
                        iteration=iteration, executions=executions, decision=decision, evidence_added=evidence_added,
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
                            "approval.required", run, step_id=planned.id, tool=planned.tool,
                            step_target=planned.target, risk=planned.risk, authority="mission_director",
                        )
                        break
                return self._finish_result(
                    plan, run, session_id=session_id, reason=LoopStopReason.APPROVAL_REQUIRED,
                    iteration=iteration, executions=executions, decision=decision,
                )

            elif decision.action is ReasoningAction.REVIEW:
                if self._legacy_plan_complete(plan, run) and run.state is MissionRunState.RUNNING:
                    run.finish(MissionRunState.SUCCEEDED)
                return self._finish_result(
                    plan, run, session_id=session_id, reason=LoopStopReason.REVIEW_REQUIRED,
                    iteration=iteration, executions=executions, decision=decision,
                )

            elif run.state in {MissionRunState.FAILED, MissionRunState.DENIED} or decision.action is ReasoningAction.STOP:
                return self._finish_result(
                    plan, run, session_id=session_id, reason=LoopStopReason.TERMINAL,
                    iteration=iteration, executions=executions, decision=decision,
                )

            elif decision.action is ReasoningAction.COMPLETE:
                if run.state not in {MissionRunState.SUCCEEDED, MissionRunState.FAILED, MissionRunState.DENIED}:
                    self._close_legacy_plan(plan, run, decision_id=decision.id)
                    run.finish(MissionRunState.SUCCEEDED)
                    self._emit("mission.completed", run, authority="mission_director")
                return self._finish_result(
                    plan, run, session_id=session_id, reason=LoopStopReason.COMPLETE,
                    iteration=iteration, executions=executions, decision=decision,
                )

            elif decision.action is ReasoningAction.CONTINUE:
                if executions >= self.policy.max_executions and self._next_step_would_execute(plan, run, approval_tokens):
                    return self._result(
                        plan, run, session_id=session_id, reason=LoopStopReason.EXECUTION_BUDGET,
                        iterations=iteration - 1, executions=executions, decision=decision,
                    )
                jobs_before = tuple(step.job_id for step in run.steps)
                self._advance_selected_legacy_once(
                    plan, run, approval_tokens=approval_tokens, step_id=decision.next_step_id,
                )
                jobs_after = tuple(step.job_id for step in run.steps)
                executions += sum(
                    1 for before_job, after_job in zip(jobs_before, jobs_after, strict=True)
                    if before_job != after_job and after_job is not None
                )
                evidence_added = len(run.evidence) - evidence_before

            max_gain = max((proposal.expected_info_gain for proposal in decision.new_proposals), default=0.0)
            report = self.convergence.observe(run, max_expected_info_gain=max_gain)
            self._emit(
                "convergence.observed", run, converged=report.converged, reason=report.reason,
                open_hypotheses=report.open_hypotheses, recent_fact_gain=report.recent_fact_gain,
                recent_proposal_gain=report.recent_proposal_gain, max_expected_info_gain=report.max_expected_info_gain,
            )
            self._record_iteration(
                run, session_id=session_id, iteration=iteration, executions=executions,
                decision=decision, evidence_added=evidence_added,
            )
            self._record_council_round(plan, run, session_id=session_id, decision=decision, phase="live")
            self._checkpoint(plan, run)

            no_progress = evidence_added == 0 and states_before == tuple(step.state for step in run.steps)
            if repeated[key] > self.policy.max_repeat_decisions and no_progress:
                return self._result(
                    plan, run, session_id=session_id, reason=LoopStopReason.REPEATED_DECISION,
                    iterations=iteration, executions=executions, decision=decision,
                )
            if run.state is MissionRunState.WAITING_APPROVAL:
                return self._result(
                    plan, run, session_id=session_id, reason=LoopStopReason.APPROVAL_REQUIRED,
                    iterations=iteration, executions=executions, decision=decision,
                )
            if run.state in {MissionRunState.FAILED, MissionRunState.DENIED}:
                return self._result(
                    plan, run, session_id=session_id, reason=LoopStopReason.TERMINAL,
                    iterations=iteration, executions=executions, decision=decision,
                )

        return self._result(
            plan, run, session_id=session_id, reason=LoopStopReason.MAX_ITERATIONS,
            iterations=self.policy.max_iterations, executions=executions, decision=last_decision,
        )
