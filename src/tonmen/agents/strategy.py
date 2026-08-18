from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from tonmen.adaptive import build_target_profile
from tonmen.core.runtime import TonmenRuntime
from tonmen.evidence import GraphNode
from tonmen.missions import MissionPlan, MissionRun, MissionRunState, MissionStep, StepExecutionState

from .planner import MissionPlanner


@dataclass(frozen=True, slots=True)
class PlanExpansion:
    """One evidence-backed capability addition; never an executable shell proposal."""

    step: MissionStep
    rationale: str
    expected_information_gain: str
    basis_fact_ids: tuple[str, ...]
    profile_unknowns: tuple[str, ...]


class AdaptiveMissionPlanner:
    """Grow a mission one governed capability at a time from recorded evidence.

    The planner selects only tools already registered in TONMEN and delegates typed
    parameter validation, Scope and Policy checks to MissionPlanner.build_step(). It
    cannot create raw shell text, expand Scope, issue approval, or bypass REPORT_ONLY.
    """

    def __init__(self, runtime: TonmenRuntime) -> None:
        self.runtime = runtime
        self.base = MissionPlanner(runtime)

    def seed(self, target: str) -> MissionPlan:
        return self.base.seed(target)

    @staticmethod
    def _queued_tools(plan: MissionPlan) -> set[str]:
        return {step.tool for step in plan.steps}

    @staticmethod
    def _completed_tools(run: MissionRun) -> set[str]:
        return {
            step.tool
            for step in run.steps
            if step.state in {StepExecutionState.SUCCEEDED, StepExecutionState.DEGRADED, StepExecutionState.SKIPPED}
        }

    @staticmethod
    def _fact_ids(run: MissionRun, *kinds: str) -> tuple[str, ...]:
        wanted = set(kinds)
        return tuple(node.id for node in run.graph.nodes.values() if node.kind in wanted)[:16]

    def _build(
        self,
        plan: MissionPlan,
        run: MissionRun,
        tool: str,
        *,
        rationale: str,
        expected_information_gain: str,
        basis_fact_ids: tuple[str, ...],
    ) -> PlanExpansion:
        profile = build_target_profile(plan, run)
        step = self.base.build_step(tool, plan.target, rationale=rationale)
        return PlanExpansion(
            step=step,
            rationale=rationale,
            expected_information_gain=expected_information_gain,
            basis_fact_ids=basis_fact_ids,
            profile_unknowns=profile.unknowns,
        )

    def propose(self, plan: MissionPlan, run: MissionRun) -> PlanExpansion | None:
        if run.plan_id != plan.id:
            raise ValueError("mission run does not belong to this plan")
        if run.state in {MissionRunState.FAILED, MissionRunState.DENIED, MissionRunState.WAITING_APPROVAL}:
            return None

        profile = build_target_profile(plan, run)
        queued = self._queued_tools(plan)
        completed = self._completed_tools(run)

        # Host/IP seeds first establish whether a Web-capable service actually exists.
        # An explicit HTTP(S) target skips this branch and begins at httpx.
        if "nmap" in completed and "httpx" not in queued and profile.has_web_surface:
            basis = self._fact_ids(run, "intelligence.service")
            return self._build(
                plan,
                run,
                "httpx",
                rationale="Network evidence exposes an HTTP-capable service; resolve the live Web surface next.",
                expected_information_gain="HTTP reachability, status, title and technology evidence",
                basis_fact_ids=basis,
            )

        if "httpx" in completed and "crawler" not in queued and profile.has_web_surface:
            basis = self._fact_ids(run, "intelligence.web", "intelligence.service")
            return self._build(
                plan,
                run,
                "crawler",
                rationale="HTTP evidence confirms a Web surface; add bounded same-origin endpoint coverage.",
                expected_information_gain="same-origin pages, routes and page metadata",
                basis_fact_ids=basis,
            )

        if "crawler" in completed and "nuclei" not in queued and profile.has_web_surface:
            basis = self._fact_ids(run, "intelligence.web")
            return self._build(
                plan,
                run,
                "nuclei",
                rationale=(
                    "Evidence-backed Web coverage is available; propose bounded template validation as the next "
                    "capability, still behind explicit human approval."
                ),
                expected_information_gain="evidence-backed vulnerability validation findings",
                basis_fact_ids=basis,
            )

        return None

    def apply(self, plan: MissionPlan, run: MissionRun, proposal: PlanExpansion) -> MissionPlan:
        """Append a proposal to both immutable plan history and mutable run state."""
        revised = plan.extend([proposal.step])
        execution = run.append_planned_step(proposal.step)

        if proposal.step.id not in run.graph.nodes:
            run.graph.add_node(
                GraphNode(
                    id=proposal.step.id,
                    kind="step",
                    label=f"{proposal.step.tool}:{proposal.step.target}",
                    metadata={
                        "risk": proposal.step.risk,
                        "requires_approval": proposal.step.requires_approval,
                        "adaptive": True,
                    },
                )
            )
            run.graph.link(run.id, "contains", proposal.step.id)

        revision_id = uuid4().hex
        run.graph.add_node(
            GraphNode(
                id=revision_id,
                kind="planning.revision",
                label=f"adaptive plan + {proposal.step.tool}",
                metadata={
                    "tool": proposal.step.tool,
                    "target": proposal.step.target,
                    "risk": proposal.step.risk,
                    "requires_approval": proposal.step.requires_approval,
                    "rationale": proposal.rationale,
                    "expected_information_gain": proposal.expected_information_gain,
                    "basis_fact_ids": list(proposal.basis_fact_ids),
                    "profile_unknowns": list(proposal.profile_unknowns),
                    "execution_authority": False,
                },
            )
        )
        run.graph.link(run.id, "replanned_by", revision_id)
        run.graph.link(revision_id, "adds_step", proposal.step.id)
        for fact_id in proposal.basis_fact_ids:
            if fact_id in run.graph.nodes:
                run.graph.link(fact_id, "supports_plan_revision", revision_id)

        execution.metadata["plan_revision_id"] = revision_id
        execution.metadata["plan_rationale"] = proposal.rationale
        execution.metadata["expected_information_gain"] = proposal.expected_information_gain
        execution.metadata["basis_fact_ids"] = list(proposal.basis_fact_ids)

        if self.runtime.events is not None:
            self.runtime.events.publish(
                "plan.revised",
                mission_id=run.id,
                plan_id=run.plan_id,
                target=run.target,
                revision_id=revision_id,
                step_id=proposal.step.id,
                tool=proposal.step.tool,
                step_target=proposal.step.target,
                risk=proposal.step.risk,
                requires_approval=proposal.step.requires_approval,
                rationale=proposal.rationale,
                expected_information_gain=proposal.expected_information_gain,
                basis_fact_ids=list(proposal.basis_fact_ids),
            )
        return revised
