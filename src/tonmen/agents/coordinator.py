from __future__ import annotations

from typing import Mapping

from tonmen.core.runtime import TonmenRuntime
from tonmen.evidence import GraphNode
from tonmen.intelligence import parse_evidence, summarize_facts
from tonmen.jobs import JobStatus
from tonmen.missions import MissionPlan
from tonmen.missions.run import MissionRun, MissionRunState, StepExecutionState
from tonmen.observations import Observation
from tonmen.tools import ToolRequest


class MissionRunDenied(RuntimeError):
    pass


class MissionCoordinator:
    """Advance a governed mission until completion, failure, denial, or an approval boundary."""

    def __init__(self, runtime: TonmenRuntime) -> None:
        if runtime.jobs is None or runtime.executor is None or runtime.scope is None:
            raise ValueError("MissionCoordinator requires the Sentinel runtime")
        self.runtime = runtime

    def run(self, plan: MissionPlan, *, approval_tokens: Mapping[str, str] | None = None) -> MissionRun:
        mission_run = MissionRun.create(plan)
        return self._advance(plan, mission_run, approval_tokens or {})

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
        return self._advance(plan, mission_run, approval_tokens or {})

    def _advance(
        self,
        plan: MissionPlan,
        mission_run: MissionRun,
        approval_tokens: Mapping[str, str],
    ) -> MissionRun:
        if self.runtime.scope is None or not self.runtime.scope.is_allowed(plan.target):
            raise MissionRunDenied("target is outside the authorized scope")

        if not mission_run.graph.nodes:
            mission_run.graph.add_node(
                GraphNode(id=mission_run.id, kind="mission", label=f"mission:{plan.target}", metadata={"plan_id": plan.id})
            )
            for step, execution in zip(plan.steps, mission_run.steps, strict=True):
                mission_run.graph.add_node(
                    GraphNode(
                        id=execution.step_id,
                        kind="step",
                        label=f"{step.tool}:{step.target}",
                        metadata={"risk": step.risk, "requires_approval": step.requires_approval},
                    )
                )
                mission_run.graph.link(mission_run.id, "contains", execution.step_id)

        mission_run.state = MissionRunState.RUNNING

        for step, execution in zip(plan.steps, mission_run.steps, strict=True):
            if execution.state is StepExecutionState.SUCCEEDED:
                continue

            token = approval_tokens.get(step.id)
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

        mission_run.finish(MissionRunState.SUCCEEDED)
        return mission_run
