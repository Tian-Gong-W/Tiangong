from __future__ import annotations

from datetime import datetime, timezone
from typing import Mapping

from tonmen.adaptive import AdaptiveParameterResolver
from tonmen.core.runtime import TonmenRuntime
from tonmen.evidence import GraphNode
from tonmen.intelligence import parse_evidence, summarize_facts
from tonmen.jobs import JobStatus
from tonmen.missions import MissionPlan
from tonmen.missions.run import MissionRun, MissionRunState, StepExecutionState
from tonmen.observations import Observation
from tonmen.reasoning import MissionReasoner, ReasoningAction, ReasoningDecision
from tonmen.tools import RiskLevel, ToolRequest


_SUCCESS_STATES = {
    StepExecutionState.SUCCEEDED,
    StepExecutionState.DEGRADED,
    StepExecutionState.SKIPPED,
}


class MissionRunDenied(RuntimeError):
    pass


class MissionCoordinator:
    """Execute governed mission steps. High-level callers decide how long to keep advancing."""

    def __init__(self, runtime: TonmenRuntime) -> None:
        if runtime.jobs is None or runtime.executor is None or runtime.scope is None:
            raise ValueError("MissionCoordinator requires the Sentinel runtime")
        self.runtime = runtime
        self.reasoner = MissionReasoner()
        self.parameter_resolver = AdaptiveParameterResolver()

    def _emit(self, event_type: str, run: MissionRun, **data: object) -> None:
        if self.runtime.events is not None:
            self.runtime.events.publish(
                event_type,
                mission_id=run.id,
                plan_id=run.plan_id,
                target=run.target,
                **data,
            )

    def _check_scope(self, plan: MissionPlan) -> None:
        if self.runtime.scope is None or not self.runtime.scope.is_allowed(plan.target):
            raise MissionRunDenied("target is outside the authorized scope")

    @staticmethod
    def _remaining_mission_seconds(run: MissionRun) -> float | None:
        """Return the remaining persisted mission wall-clock budget, when loop-governed.

        The budget intentionally uses MissionRun.started_at, so approval waits and resume
        sessions cannot silently reset a mission-wide duration boundary. The MissionLoop
        still performs its own monotonic iteration checks; this value additionally caps
        each synchronous tool invocation at the remaining global wall-clock budget.
        """
        sessions = [node for node in run.graph.nodes.values() if node.kind == "loop.session"]
        if not sessions:
            return None
        try:
            maximum = float(sessions[-1].metadata.get("max_duration_seconds", 0))
        except (TypeError, ValueError):
            return None
        if maximum <= 0:
            return None
        elapsed = max(0.0, (datetime.now(timezone.utc) - run.started_at).total_seconds())
        return max(0.001, maximum - elapsed)

    @staticmethod
    def _ensure_graph(plan: MissionPlan, run: MissionRun) -> None:
        if run.graph.nodes:
            return
        run.graph.add_node(
            GraphNode(
                id=run.id,
                kind="mission",
                label=f"mission:{plan.target}",
                metadata={"plan_id": plan.id},
            )
        )
        for step, execution in zip(plan.steps, run.steps, strict=True):
            run.graph.add_node(
                GraphNode(
                    id=execution.step_id,
                    kind="step",
                    label=f"{step.tool}:{step.target}",
                    metadata={"risk": step.risk, "requires_approval": step.requires_approval},
                )
            )
            run.graph.link(run.id, "contains", execution.step_id)

    @staticmethod
    def record_reasoning(run: MissionRun, decision: ReasoningDecision) -> None:
        run.graph.add_node(
            GraphNode(
                id=decision.id,
                kind=f"reasoning.{decision.action.value}",
                label=decision.summary,
                metadata={
                    "action": decision.action.value,
                    "basis_fact_ids": list(decision.basis_fact_ids),
                    "next_step_id": decision.next_step_id,
                    "requires_human": decision.requires_human,
                },
            )
        )
        run.graph.link(run.id, "decided", decision.id)
        for fact_id in decision.basis_fact_ids:
            if fact_id in run.graph.nodes:
                run.graph.link(fact_id, "supports_decision", decision.id)
        if decision.next_step_id and decision.next_step_id in run.graph.nodes:
            run.graph.link(decision.id, "recommends", decision.next_step_id)

    @staticmethod
    def apply_reasoning_decision(plan: MissionPlan, run: MissionRun, decision: ReasoningDecision) -> bool:
        if decision.action is not ReasoningAction.SKIP or not decision.next_step_id:
            return False
        for planned, execution in zip(plan.steps, run.steps, strict=True):
            if planned.id != decision.next_step_id:
                continue
            if execution.state not in {StepExecutionState.PENDING, StepExecutionState.WAITING_APPROVAL}:
                return False
            preflight = execution.metadata.get("preflight")
            if isinstance(preflight, dict) and preflight.get("ready") is False:
                return False
            execution.state = StepExecutionState.SKIPPED
            execution.error = None
            execution.metadata["reasoning_decision_id"] = decision.id
            if all(item.state in _SUCCESS_STATES for item in run.steps):
                run.finish(MissionRunState.SUCCEEDED)
            else:
                run.state = MissionRunState.RUNNING
            return True
        return False

    @staticmethod
    def _record_execution_evidence(run: MissionRun, execution, evidence) -> None:
        if all(item.id != evidence.id for item in run.evidence):
            run.evidence.append(evidence)
        execution.evidence_id = evidence.id
        execution.metadata["exit_code"] = evidence.exit_code
        if evidence.id not in run.graph.nodes:
            run.graph.add_node(
                GraphNode(
                    id=evidence.id,
                    kind="evidence",
                    label=f"evidence:{execution.tool}",
                    metadata={"exit_code": evidence.exit_code, "argv": evidence.argv},
                )
            )
            run.graph.link(execution.step_id, "produced", evidence.id)

    def _settle_success(self, mission_run: MissionRun, *, defer_success: bool) -> None:
        if not all(item.state in _SUCCESS_STATES for item in mission_run.steps):
            mission_run.state = MissionRunState.RUNNING
            return
        if defer_success:
            mission_run.state = MissionRunState.RUNNING
            mission_run.finished_at = None
            return
        mission_run.finish(MissionRunState.SUCCEEDED)
        self._emit("mission.completed", mission_run)

    def start(self, plan: MissionPlan) -> MissionRun:
        self._check_scope(plan)
        run = MissionRun.create(plan)
        self._ensure_graph(plan, run)
        run.state = MissionRunState.RUNNING
        self._emit("mission.started", run, steps=len(plan.steps))
        return run

    def run(self, plan: MissionPlan, *, approval_tokens: Mapping[str, str] | None = None) -> MissionRun:
        run = self.start(plan)
        return self._drive(plan, run, approval_tokens or {})

    def resume(
        self,
        plan: MissionPlan,
        mission_run: MissionRun,
        *,
        approval_tokens: Mapping[str, str] | None = None,
    ) -> MissionRun:
        if mission_run.plan_id != plan.id:
            raise ValueError("mission run does not belong to this plan")
        if mission_run.state is not MissionRunState.WAITING_APPROVAL:
            raise ValueError("only a mission waiting for approval can be resumed")
        self._emit("mission.resumed", mission_run)
        return self._drive(plan, mission_run, approval_tokens or {})

    def _preflight_step(self, step, execution, mission_run: MissionRun, token: str | None) -> bool:
        if self.runtime.executor is not None and not self.runtime.executor.uses_local_subprocess:
            execution.metadata.pop("preflight", None)
            return True

        adapter = self.runtime.registry.get(step.tool)
        readiness = adapter.readiness()
        if readiness.ready:
            execution.metadata.pop("preflight", None)
            return True

        if token and self.runtime.approvals is not None:
            self.runtime.approvals.revoke(token)

        execution.error = f"tool preflight blocked: {readiness.detail}"
        execution.metadata["preflight"] = {
            "ready": False,
            "code": readiness.code,
            "detail": readiness.detail,
            "remediation": readiness.remediation,
            "metadata": dict(readiness.metadata),
        }
        self._emit(
            "tool.preflight_blocked",
            mission_run,
            step_id=step.id,
            tool=step.tool,
            step_target=step.target,
            code=readiness.code,
            detail=readiness.detail,
            remediation=readiness.remediation,
        )

        if step.requires_approval:
            execution.state = StepExecutionState.WAITING_APPROVAL
            mission_run.state = MissionRunState.WAITING_APPROVAL
            return False

        execution.state = StepExecutionState.FAILED
        mission_run.finish(MissionRunState.FAILED)
        self._emit("step.failed", mission_run, step_id=step.id, tool=step.tool, error=execution.error)
        self._emit("mission.failed", mission_run)
        return False

    def advance_once(
        self,
        plan: MissionPlan,
        mission_run: MissionRun,
        *,
        approval_tokens: Mapping[str, str] | None = None,
        defer_success: bool = False,
    ) -> MissionRun:
        if mission_run.plan_id != plan.id:
            raise ValueError("mission run does not belong to this plan")
        self._check_scope(plan)
        self._ensure_graph(plan, mission_run)
        if mission_run.state in {MissionRunState.SUCCEEDED, MissionRunState.FAILED, MissionRunState.DENIED}:
            return mission_run

        tokens = approval_tokens or {}
        mission_run.state = MissionRunState.RUNNING
        for step, execution in zip(plan.steps, mission_run.steps, strict=True):
            if execution.state in _SUCCESS_STATES:
                continue

            if execution.state is StepExecutionState.PENDING:
                justified, justification = self.parameter_resolver.justify(plan, mission_run, step)
                if not justified:
                    execution.state = StepExecutionState.SKIPPED
                    execution.error = None
                    execution.metadata["adaptive_skip_reason"] = justification
                    profile = self.parameter_resolver.profile(plan, mission_run)
                    execution.metadata["adaptive_profile"] = {
                        "kind": profile.target_kind,
                        "complexity": profile.complexity,
                        "unknowns": list(profile.unknowns),
                        "hypotheses": [item.key for item in profile.hypotheses],
                    }
                    self._emit(
                        "step.skipped",
                        mission_run,
                        step_id=step.id,
                        tool=step.tool,
                        reason=justification,
                        adaptive=True,
                    )
                    self._settle_success(mission_run, defer_success=defer_success)
                    return mission_run

            token = tokens.get(step.id)
            if step.requires_approval and not token:
                execution.state = StepExecutionState.WAITING_APPROVAL
                execution.error = "explicit approval grant required"
                mission_run.state = MissionRunState.WAITING_APPROVAL
                self._emit(
                    "approval.required",
                    mission_run,
                    step_id=step.id,
                    tool=step.tool,
                    step_target=step.target,
                    risk=step.risk,
                )
                return mission_run

            if not self._preflight_step(step, execution, mission_run, token):
                return mission_run

            resolved_parameters = self.parameter_resolver.resolve(plan, mission_run, step)
            profile = self.parameter_resolver.profile(plan, mission_run)
            execution.metadata["planned_parameters"] = dict(step.parameters)
            execution.metadata["resolved_parameters"] = dict(resolved_parameters)
            execution.metadata["adaptive_profile"] = {
                "kind": profile.target_kind,
                "complexity": profile.complexity,
                "unknowns": list(profile.unknowns),
                "hypotheses": [item.key for item in profile.hypotheses],
            }

            remaining_seconds = self._remaining_mission_seconds(mission_run)
            request_context: dict[str, object] = {
                "mission_id": mission_run.id,
                "plan_id": mission_run.plan_id,
                "step_id": step.id,
                "adaptive": True,
                "profile_complexity": profile.complexity,
            }
            if remaining_seconds is not None:
                request_context["execution_timeout_seconds"] = remaining_seconds
                execution.metadata["mission_remaining_seconds_at_start"] = round(remaining_seconds, 6)

            request = ToolRequest(
                tool=step.tool,
                target=step.target,
                parameters=resolved_parameters,
                context=request_context,
            )
            execution.state = StepExecutionState.RUNNING
            execution.error = None
            self._emit(
                "step.started",
                mission_run,
                step_id=step.id,
                tool=step.tool,
                step_target=step.target,
                risk=step.risk,
                parameters=dict(resolved_parameters),
                profile_complexity=profile.complexity,
                profile_unknowns=list(profile.unknowns),
                mission_remaining_seconds=remaining_seconds,
            )
            job = self.runtime.jobs.submit(request, approval_token=token)
            execution.job_id = job.id

            if job.status is JobStatus.DENIED:
                execution.state = StepExecutionState.DENIED
                execution.error = job.error or "execution denied"
                mission_run.finish(MissionRunState.DENIED)
                self._emit("step.denied", mission_run, step_id=step.id, tool=step.tool, error=execution.error)
                self._emit("mission.denied", mission_run)
                return mission_run

            if job.status is not JobStatus.SUCCEEDED or job.outcome is None:
                execution.state = StepExecutionState.FAILED
                if job.outcome is not None:
                    self._record_execution_evidence(mission_run, execution, job.outcome.evidence)
                    self._emit(
                        "evidence.created",
                        mission_run,
                        step_id=step.id,
                        tool=step.tool,
                        evidence_id=job.outcome.evidence.id,
                        exit_code=job.outcome.evidence.exit_code,
                    )
                    execution.error = job.error or job.outcome.result.summary
                    timed_out = bool(job.outcome.result.evidence.get("timed_out"))
                    if timed_out and step.risk <= int(RiskLevel.DISCOVERY):
                        execution.state = StepExecutionState.DEGRADED
                        execution.metadata["timed_out"] = True
                        execution.metadata["timeout_seconds"] = job.outcome.result.evidence.get("timeout_seconds")
                        execution.metadata["degraded_reason"] = "discovery_timeout"
                        mission_run.state = MissionRunState.RUNNING
                        self._emit(
                            "step.degraded",
                            mission_run,
                            step_id=step.id,
                            tool=step.tool,
                            error=execution.error,
                            reason="discovery_timeout",
                            evidence_id=job.outcome.evidence.id,
                        )
                        return mission_run
                else:
                    execution.error = job.error or "execution failed"
                mission_run.finish(MissionRunState.FAILED)
                self._emit("step.failed", mission_run, step_id=step.id, tool=step.tool, error=execution.error)
                self._emit("mission.failed", mission_run)
                return mission_run

            outcome = job.outcome
            evidence = outcome.evidence
            self._record_execution_evidence(mission_run, execution, evidence)
            self._emit(
                "evidence.created",
                mission_run,
                step_id=step.id,
                tool=step.tool,
                evidence_id=evidence.id,
                exit_code=evidence.exit_code,
            )

            facts = parse_evidence(evidence)
            observation = Observation.create(
                source=step.tool,
                target=step.target,
                summary=summarize_facts(step.tool, facts, outcome.result.summary),
                evidence_id=evidence.id,
                metadata={
                    "exit_code": evidence.exit_code,
                    "job_id": job.id,
                    "fact_ids": [fact.id for fact in facts],
                },
            )
            mission_run.observations.append(observation)
            execution.state = StepExecutionState.SUCCEEDED
            execution.observation_id = observation.id
            execution.metadata["fact_ids"] = [fact.id for fact in facts]
            mission_run.graph.add_node(
                GraphNode(
                    id=observation.id,
                    kind="observation",
                    label=observation.summary,
                    metadata={"source": observation.source, "target": observation.target},
                )
            )
            mission_run.graph.link(evidence.id, "supports", observation.id)
            mission_run.graph.link(mission_run.id, "observed", observation.id)
            self._emit(
                "observation.created",
                mission_run,
                step_id=step.id,
                observation_id=observation.id,
                evidence_id=evidence.id,
                summary=observation.summary,
            )

            for fact in facts:
                mission_run.graph.add_node(
                    GraphNode(
                        id=fact.id,
                        kind=f"intelligence.{fact.kind.value}",
                        label=fact.title,
                        metadata={
                            "source": fact.source,
                            "target": fact.target,
                            "severity": fact.severity.value,
                            "confidence": fact.confidence,
                            "evidence_id": fact.evidence_id,
                            "data": dict(fact.data),
                        },
                    )
                )
                mission_run.graph.link(evidence.id, "reveals", fact.id)
                mission_run.graph.link(observation.id, "summarizes", fact.id)
                mission_run.graph.link(mission_run.id, "knows", fact.id)
                self._emit(
                    "intelligence.created",
                    mission_run,
                    step_id=step.id,
                    fact_id=fact.id,
                    kind=fact.kind.value,
                    title=fact.title,
                    severity=fact.severity.value,
                    evidence_id=fact.evidence_id,
                )

            self._emit(
                "step.completed",
                mission_run,
                step_id=step.id,
                tool=step.tool,
                evidence_id=evidence.id,
                observation_id=observation.id,
                facts=len(facts),
            )
            self._settle_success(mission_run, defer_success=defer_success)
            return mission_run

        self._settle_success(mission_run, defer_success=defer_success)
        return mission_run

    def _drive(self, plan: MissionPlan, run: MissionRun, approval_tokens: Mapping[str, str]) -> MissionRun:
        safety_limit = max(4, len(plan.steps) * 3 + 2)
        for _ in range(safety_limit):
            before = (run.state, tuple(step.state for step in run.steps), len(run.evidence))
            self.advance_once(plan, run, approval_tokens=approval_tokens)
            decision = self.reasoner.decide(plan, run)
            self.record_reasoning(run, decision)
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
            if decision.action is ReasoningAction.SKIP and self.apply_reasoning_decision(plan, run, decision):
                self._emit("step.skipped", run, step_id=decision.next_step_id, reason=decision.summary)
                continue
            if run.state in {
                MissionRunState.WAITING_APPROVAL,
                MissionRunState.SUCCEEDED,
                MissionRunState.FAILED,
                MissionRunState.DENIED,
            }:
                return run
            after = (run.state, tuple(step.state for step in run.steps), len(run.evidence))
            if after == before:
                raise RuntimeError("mission coordinator made no progress")
        raise RuntimeError("mission coordinator safety limit reached")
