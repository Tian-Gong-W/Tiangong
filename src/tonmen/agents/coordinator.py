from __future__ import annotations

from typing import Mapping

from tonmen.core.runtime import TonmenRuntime
from tonmen.evidence import GraphNode
from tonmen.intelligence import parse_evidence, summarize_facts
from tonmen.jobs import JobStatus
from tonmen.missions import MissionPlan
from tonmen.missions.run import MissionRun, MissionRunState, StepExecutionState
from tonmen.observations import Observation
from tonmen.reasoning import MissionReasoner, ReasoningAction, ReasoningDecision
from tonmen.tools import ToolRequest


class MissionRunDenied(RuntimeError):
    pass


class MissionCoordinator:
    """Execute governed mission steps. High-level callers decide how long to keep advancing."""

    def __init__(self, runtime: TonmenRuntime) -> None:
        if runtime.jobs is None or runtime.executor is None or runtime.scope is None:
            raise ValueError("MissionCoordinator requires the Sentinel runtime")
        self.runtime = runtime
        self.reasoner = MissionReasoner()

    def _check_scope(self, plan: MissionPlan) -> None:
        if self.runtime.scope is None or not self.runtime.scope.is_allowed(plan.target):
            raise MissionRunDenied("target is outside the authorized scope")

    @staticmethod
    def _ensure_graph(plan: MissionPlan, run: MissionRun) -> None:
        if run.graph.nodes:
            return
        run.graph.add_node(
            GraphNode(id=run.id, kind="mission", label=f"mission:{plan.target}", metadata={"plan_id": plan.id})
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
        """Apply only bounded autonomous decisions. This method never grants approval."""
        if decision.action is not ReasoningAction.SKIP or not decision.next_step_id:
            return False
        for planned, execution in zip(plan.steps, run.steps, strict=True):
            if planned.id != decision.next_step_id:
                continue
            if execution.state not in {StepExecutionState.PENDING, StepExecutionState.WAITING_APPROVAL}:
                return False
            execution.state = StepExecutionState.SKIPPED
            execution.error = None
            execution.metadata["reasoning_decision_id"] = decision.id
            run.state = MissionRunState.RUNNING
            return True
        return False

    def start(self, plan: MissionPlan) -> MissionRun:
        self._check_scope(plan)
        run = MissionRun.create(plan)
        self._ensure_graph(plan, run)
        run.state = MissionRunState.RUNNING
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
        return self._drive(plan, mission_run, approval_tokens or {})

    def advance_once(
        self,
        plan: MissionPlan,
        mission_run: MissionRun,
        *,
        approval_tokens: Mapping[str, str] | None = None,
    ) -> MissionRun:
        """Advance at most one planned tool execution, or stop at one governance boundary."""
        if mission_run.plan_id != plan.id:
            raise ValueError("mission run does not belong to this plan")
        self._check_scope(plan)
        self._ensure_graph(plan, mission_run)

        if mission_run.state in {MissionRunState.SUCCEEDED, MissionRunState.FAILED, MissionRunState.DENIED}:
            return mission_run

        tokens = approval_tokens or {}
        mission_run.state = MissionRunState.RUNNING

        for step, execution in zip(plan.steps, mission_run.steps, strict=True):
            if execution.state in {StepExecutionState.SUCCEEDED, StepExecutionState.SKIPPED}:
                continue

            token = tokens.get(step.id)
            if step.requires_approval and not token:
                execution.state = StepExecutionState.WAITING_APPROVAL
                execution.error = "explicit approval grant required"
                mission_run.state = MissionRunState.WAITING_APPROVAL
                return mission_run

            request = ToolRequest(tool=step.tool, target=step.target, parameters=step.parameters)
            execution.state = StepExecutionState.RUNNING
            execution.error = None
            job = self.runtime.jobs.submit(request, approval_token=token)
            execution.job_id = job.id

            if job.status is JobStatus.DENIED:
                execution.state = StepExecutionState.DENIED
                execution.error = job.error or "execution denied"
                mission_run.finish(MissionRunState.DENIED)
                return mission_run

            if job.status is not JobStatus.SUCCEEDED or job.outcome is None:
                execution.state = StepExecutionState.FAILED
                execution.error = job.error or "execution failed"
                mission_run.finish(MissionRunState.FAILED)
                return mission_run

            outcome = job.outcome
            evidence = outcome.evidence
            mission_run.evidence.append(evidence)

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
            execution.evidence_id = evidence.id
            execution.observation_id = observation.id
            execution.metadata["exit_code"] = evidence.exit_code
            execution.metadata["fact_ids"] = [fact.id for fact in facts]

            mission_run.graph.add_node(
                GraphNode(
                    id=evidence.id,
                    kind="evidence",
                    label=f"evidence:{step.tool}",
                    metadata={"exit_code": evidence.exit_code, "argv": evidence.argv},
                )
            )
            mission_run.graph.add_node(
                GraphNode(
                    id=observation.id,
                    kind="observation",
                    label=observation.summary,
                    metadata={"source": observation.source, "target": observation.target},
                )
            )
            mission_run.graph.link(execution.step_id, "produced", evidence.id)
            mission_run.graph.link(evidence.id, "supports", observation.id)
            mission_run.graph.link(mission_run.id, "observed", observation.id)

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

            if all(
                item.state in {StepExecutionState.SUCCEEDED, StepExecutionState.SKIPPED}
                for item in mission_run.steps
            ):
                mission_run.finish(MissionRunState.SUCCEEDED)
            else:
                mission_run.state = MissionRunState.RUNNING
            return mission_run

        mission_run.finish(MissionRunState.SUCCEEDED)
        return mission_run

    def _drive(
        self,
        plan: MissionPlan,
        run: MissionRun,
        approval_tokens: Mapping[str, str],
    ) -> MissionRun:
        """Backward-compatible run-to-boundary behavior built on single-step advancement."""
        safety_limit = max(4, len(plan.steps) * 3 + 2)
        for _ in range(safety_limit):
            before = (run.state, tuple(step.state for step in run.steps), len(run.evidence))
            self.advance_once(plan, run, approval_tokens=approval_tokens)
            decision = self.reasoner.decide(plan, run)
            self.record_reasoning(run, decision)

            if decision.action is ReasoningAction.SKIP and self.apply_reasoning_decision(plan, run, decision):
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
