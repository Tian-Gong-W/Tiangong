from __future__ import annotations

from time import monotonic
from typing import Callable, Mapping
from uuid import uuid4

from tonmen.agents import MissionCoordinator
from tonmen.core.runtime import TonmenRuntime
from tonmen.council import AssessmentCouncil
from tonmen.evidence import GraphNode
from tonmen.missions import MissionPlan, MissionRun, MissionRunState
from tonmen.reasoning import MissionReasoner, ReasoningAction, ReasoningDecision

from .model import LoopStopReason, MissionLoopPolicy, MissionLoopResult


class MissionLoop:
    """Bounded observe → reason → act loop over existing governed mission steps only."""

    def __init__(
        self,
        runtime: TonmenRuntime,
        policy: MissionLoopPolicy | None = None,
        *,
        checkpoint: Callable[[MissionPlan, MissionRun], None] | None = None,
    ) -> None:
        self.runtime = runtime
        self.policy = policy or MissionLoopPolicy()
        self.coordinator = MissionCoordinator(runtime)
        self.reasoner = MissionReasoner()
        self.council = AssessmentCouncil(
            target_rounds=self.policy.assessment_rounds,
            agents_per_round=self.policy.subagents_per_round,
        )
        self.checkpoint = checkpoint

    def _emit(self, event_type: str, run: MissionRun, **data: object) -> None:
        if self.runtime.events is not None:
            self.runtime.events.publish(
                event_type,
                mission_id=run.id,
                plan_id=run.plan_id,
                target=run.target,
                **data,
            )

    def _checkpoint(self, plan: MissionPlan, run: MissionRun) -> None:
        if self.checkpoint is not None:
            self.checkpoint(plan, run)

    def run(self, plan: MissionPlan) -> MissionLoopResult:
        run = self.coordinator.start(plan)
        self._checkpoint(plan, run)
        return self._drive(plan, run, approval_tokens={})

    def resume(
        self,
        plan: MissionPlan,
        run: MissionRun,
        *,
        approval_tokens: Mapping[str, str] | None = None,
    ) -> MissionLoopResult:
        if run.plan_id != plan.id:
            raise ValueError("mission run does not belong to this plan")
        if run.state in {MissionRunState.SUCCEEDED, MissionRunState.FAILED, MissionRunState.DENIED}:
            raise ValueError("terminal mission cannot enter a new loop session")
        return self._drive(plan, run, approval_tokens=approval_tokens or {})

    @staticmethod
    def _decision_key(decision: ReasoningDecision) -> tuple[object, ...]:
        return (
            decision.action.value,
            decision.next_step_id,
            decision.basis_fact_ids,
            decision.requires_human,
        )

    @staticmethod
    def _has_unfinished_steps(run: MissionRun) -> bool:
        return run.state not in {MissionRunState.SUCCEEDED, MissionRunState.FAILED, MissionRunState.DENIED}

    @staticmethod
    def _next_step_would_execute(
        plan: MissionPlan,
        run: MissionRun,
        approval_tokens: Mapping[str, str],
    ) -> bool:
        from tonmen.missions import StepExecutionState

        for planned, execution in zip(plan.steps, run.steps, strict=True):
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

    def _record_session(self, run: MissionRun, session_id: str) -> None:
        run.graph.add_node(
            GraphNode(
                id=session_id,
                kind="loop.session",
                label="天衡 bounded mission loop",
                metadata={
                    "max_iterations": self.policy.max_iterations,
                    "max_executions": self.policy.max_executions,
                    "max_repeat_decisions": self.policy.max_repeat_decisions,
                    "max_duration_seconds": self.policy.max_duration_seconds,
                    "assessment_rounds": self.policy.assessment_rounds,
                    "subagents_per_round": self.policy.subagents_per_round,
                    "report_only": self.policy.report_only,
                    "assessment_round_bounds": [7, 10],
                    "subagent_bounds": [3, 5],
                },
            )
        )
        run.graph.link(run.id, "governed_by", session_id)
        self._emit(
            "loop.session",
            run,
            session_id=session_id,
            max_iterations=self.policy.max_iterations,
            max_executions=self.policy.max_executions,
            max_repeat_decisions=self.policy.max_repeat_decisions,
            max_duration_seconds=self.policy.max_duration_seconds,
            assessment_rounds=self.policy.assessment_rounds,
            subagents_per_round=self.policy.subagents_per_round,
            report_only=self.policy.report_only,
        )

    def _record_iteration(
        self,
        run: MissionRun,
        *,
        session_id: str,
        iteration: int,
        executions: int,
        decision: ReasoningDecision,
        evidence_added: int,
    ) -> None:
        node_id = uuid4().hex
        run.graph.add_node(
            GraphNode(
                id=node_id,
                kind="loop.iteration",
                label=f"iteration {iteration}: {decision.action.value}",
                metadata={
                    "iteration": iteration,
                    "executions": executions,
                    "decision_id": decision.id,
                    "decision_action": decision.action.value,
                    "evidence_added": evidence_added,
                },
            )
        )
        run.graph.link(session_id, "contains_iteration", node_id)
        if decision.id in run.graph.nodes:
            run.graph.link(node_id, "observed_decision", decision.id)
        self._emit(
            "loop.iteration",
            run,
            session_id=session_id,
            iteration=iteration,
            executions=executions,
            decision_id=decision.id,
            decision_action=decision.action.value,
            evidence_added=evidence_added,
        )

    def _record_council_round(
        self,
        plan: MissionPlan,
        run: MissionRun,
        *,
        session_id: str,
        decision: ReasoningDecision | None,
        phase: str,
    ) -> None:
        before = sum(1 for node in run.graph.nodes.values() if node.kind == "council.round")
        round_id = self.council.record_round(
            plan,
            run,
            session_id=session_id,
            phase=phase,
            decision_id=decision.id if decision else None,
        )
        if round_id is None:
            return
        after = sum(1 for node in run.graph.nodes.values() if node.kind == "council.round")
        round_node = run.graph.nodes.get(round_id)
        actual_agents = self.policy.subagents_per_round
        desired_rounds = self.policy.assessment_rounds
        if round_node is not None:
            actual_agents = int(round_node.metadata.get("agents", actual_agents))
            desired_rounds = int(round_node.metadata.get("desired_rounds", desired_rounds))
        self._emit(
            "council.round",
            run,
            session_id=session_id,
            round=after,
            phase=phase,
            subagents=actual_agents,
            desired_rounds=desired_rounds,
            added=after - before,
        )

    def _record_report_gate(self, run: MissionRun, *, session_id: str) -> None:
        if any(node.kind == "governance.report_gate" for node in run.graph.nodes.values()):
            return
        node_id = uuid4().hex
        run.graph.add_node(
            GraphNode(
                id=node_id,
                kind="governance.report_gate",
                label="report-only boundary: final active actions disabled",
                metadata={
                    "report_only": True,
                    "final_active_action": False,
                    "payload_execution": False,
                    "credential_capture": False,
                    "session_takeover": False,
                    "persistence": False,
                },
            )
        )
        run.graph.link(run.id, "stopped_before_final_action_by", node_id)
        if session_id in run.graph.nodes:
            run.graph.link(session_id, "enforces", node_id)
        self._emit("governance.report_gate", run, session_id=session_id, report_only=True)

    def _record_stop(
        self,
        run: MissionRun,
        *,
        session_id: str,
        reason: LoopStopReason,
        iterations: int,
        executions: int,
        decision: ReasoningDecision | None,
    ) -> None:
        node_id = uuid4().hex
        run.graph.add_node(
            GraphNode(
                id=node_id,
                kind="loop.stop",
                label=f"loop stopped: {reason.value}",
                metadata={
                    "reason": reason.value,
                    "iterations": iterations,
                    "executions": executions,
                    "decision_id": decision.id if decision else None,
                    "report_only": self.policy.report_only,
                },
            )
        )
        run.graph.link(session_id, "stopped_by", node_id)
        if decision and decision.id in run.graph.nodes:
            run.graph.link(decision.id, "caused_stop", node_id)
        self._emit(
            "loop.stopped",
            run,
            session_id=session_id,
            reason=reason.value,
            iterations=iterations,
            executions=executions,
            decision_id=decision.id if decision else None,
            report_only=self.policy.report_only,
        )

    def _result(
        self,
        plan: MissionPlan,
        run: MissionRun,
        *,
        session_id: str,
        reason: LoopStopReason,
        iterations: int,
        executions: int,
        decision: ReasoningDecision | None,
    ) -> MissionLoopResult:
        if run.state in {MissionRunState.SUCCEEDED, MissionRunState.FAILED, MissionRunState.DENIED}:
            before = sum(1 for node in run.graph.nodes.values() if node.kind == "council.round")
            added = self.council.complete_terminal_review(plan, run, session_id=session_id)
            if added:
                self._emit(
                    "council.completed",
                    run,
                    session_id=session_id,
                    rounds_before=before,
                    rounds_after=before + added,
                    subagents_per_round=self.policy.subagents_per_round,
                )
        self._record_report_gate(run, session_id=session_id)
        self._record_stop(
            run,
            session_id=session_id,
            reason=reason,
            iterations=iterations,
            executions=executions,
            decision=decision,
        )
        self._checkpoint(plan, run)
        return MissionLoopResult(
            run=run,
            stop_reason=reason,
            iterations=iterations,
            executions=executions,
            session_id=session_id,
            last_decision=decision,
        )

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

            if (
                executions >= self.policy.max_executions
                and self._has_unfinished_steps(run)
                and self._next_step_would_execute(plan, run, approval_tokens)
            ):
                return self._result(
                    plan,
                    run,
                    session_id=session_id,
                    reason=LoopStopReason.EXECUTION_BUDGET,
                    iterations=iteration - 1,
                    executions=executions,
                    decision=last_decision,
                )

            evidence_before = len(run.evidence)
            jobs_before = tuple(step.job_id for step in run.steps)
            states_before = tuple(step.state for step in run.steps)

            self.coordinator.advance_once(plan, run, approval_tokens=approval_tokens)
            evidence_added = len(run.evidence) - evidence_before
            jobs_after = tuple(step.job_id for step in run.steps)
            executions += sum(
                1
                for before_job, after_job in zip(jobs_before, jobs_after, strict=True)
                if before_job != after_job and after_job is not None
            )

            decision = self.reasoner.decide(plan, run)
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
            )
            self._record_iteration(
                run,
                session_id=session_id,
                iteration=iteration,
                executions=executions,
                decision=decision,
                evidence_added=evidence_added,
            )
            self._record_council_round(
                plan,
                run,
                session_id=session_id,
                decision=decision,
                phase="live",
            )
            self._checkpoint(plan, run)

            key = self._decision_key(decision)
            repeated[key] = repeated.get(key, 0) + 1
            no_progress = evidence_added == 0 and states_before == tuple(step.state for step in run.steps)
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

            if decision.action is ReasoningAction.SKIP:
                if self.coordinator.apply_reasoning_decision(plan, run, decision):
                    self._emit(
                        "step.skipped",
                        run,
                        step_id=decision.next_step_id,
                        reason=decision.summary,
                    )
                    self._checkpoint(plan, run)
                    continue

            if run.state is MissionRunState.WAITING_APPROVAL or decision.action is ReasoningAction.REQUEST_APPROVAL:
                return self._result(
                    plan,
                    run,
                    session_id=session_id,
                    reason=LoopStopReason.APPROVAL_REQUIRED,
                    iterations=iteration,
                    executions=executions,
                    decision=decision,
                )

            if decision.action is ReasoningAction.REVIEW:
                return self._result(
                    plan,
                    run,
                    session_id=session_id,
                    reason=LoopStopReason.REVIEW_REQUIRED,
                    iterations=iteration,
                    executions=executions,
                    decision=decision,
                )

            if run.state in {MissionRunState.FAILED, MissionRunState.DENIED} or decision.action is ReasoningAction.STOP:
                return self._result(
                    plan,
                    run,
                    session_id=session_id,
                    reason=LoopStopReason.TERMINAL,
                    iterations=iteration,
                    executions=executions,
                    decision=decision,
                )

            if run.state is MissionRunState.SUCCEEDED or decision.action is ReasoningAction.COMPLETE:
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
