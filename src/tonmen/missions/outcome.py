from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping
from uuid import uuid4

from tonmen.evidence import GraphNode

from .run import MissionRun, StepExecution, StepExecutionState


class ActionOutcomeKind(str, Enum):
    """Why one runtime Action ended in its current state.

    The distinction is epistemic: environment/authority failures must not be
    interpreted as evidence that a research hypothesis is false.
    """

    SUCCESS = "success"
    DEGRADED = "degraded"
    TECHNICAL_FAILURE = "technical_failure"
    TOOL_UNAVAILABLE = "tool_unavailable"
    POLICY_DENIED = "policy_denied"
    OUT_OF_SCOPE = "out_of_scope"
    APPROVAL_REQUIRED = "approval_required"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    LOW_INFORMATION_GAIN = "low_information_gain"
    HYPOTHESIS_INVALIDATED = "hypothesis_invalidated"


_ENVIRONMENTAL_KINDS = {
    ActionOutcomeKind.TECHNICAL_FAILURE,
    ActionOutcomeKind.TOOL_UNAVAILABLE,
    ActionOutcomeKind.POLICY_DENIED,
    ActionOutcomeKind.OUT_OF_SCOPE,
    ActionOutcomeKind.APPROVAL_REQUIRED,
}

_EVIDENCE_BEARING_KINDS = {
    ActionOutcomeKind.SUCCESS,
    ActionOutcomeKind.DEGRADED,
    ActionOutcomeKind.INSUFFICIENT_EVIDENCE,
    ActionOutcomeKind.HYPOTHESIS_INVALIDATED,
}


@dataclass(frozen=True, slots=True)
class ActionOutcome:
    id: str
    action_id: str
    kind: ActionOutcomeKind
    summary: str
    tool: str
    target: str
    proposal_id: str | None = None
    evidence_id: str | None = None
    fact_ids: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        *,
        action_id: str,
        kind: ActionOutcomeKind,
        summary: str,
        tool: str,
        target: str,
        proposal_id: str | None = None,
        evidence_id: str | None = None,
        fact_ids: tuple[str, ...] | list[str] = (),
        metadata: Mapping[str, Any] | None = None,
    ) -> "ActionOutcome":
        return cls(
            id=uuid4().hex,
            action_id=action_id,
            kind=kind,
            summary=str(summary),
            tool=str(tool),
            target=str(target),
            proposal_id=proposal_id,
            evidence_id=evidence_id,
            fact_ids=tuple(str(item) for item in fact_ids),
            metadata=dict(metadata or {}),
        )

    @property
    def environmental(self) -> bool:
        return self.kind in _ENVIRONMENTAL_KINDS

    @property
    def evidence_bearing(self) -> bool:
        return self.kind in _EVIDENCE_BEARING_KINDS

    @property
    def may_revise_belief(self) -> bool:
        """Whether this result may legitimately participate in belief updates.

        A failed execution, missing binary, denied authority or approval wait says
        nothing about whether the underlying hypothesis is true.
        """
        return self.evidence_bearing

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "action_id": self.action_id,
            "kind": self.kind.value,
            "summary": self.summary,
            "tool": self.tool,
            "target": self.target,
            "proposal_id": self.proposal_id,
            "evidence_id": self.evidence_id,
            "fact_ids": list(self.fact_ids),
            "environmental": self.environmental,
            "evidence_bearing": self.evidence_bearing,
            "may_revise_belief": self.may_revise_belief,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_graph_node(cls, node: GraphNode) -> "ActionOutcome":
        metadata = dict(node.metadata)
        return cls(
            id=node.id,
            action_id=str(metadata.get("action_id") or ""),
            kind=ActionOutcomeKind(str(metadata["kind"])),
            summary=node.label,
            tool=str(metadata.get("tool") or ""),
            target=str(metadata.get("target") or ""),
            proposal_id=str(metadata["proposal_id"]) if metadata.get("proposal_id") else None,
            evidence_id=str(metadata["evidence_id"]) if metadata.get("evidence_id") else None,
            fact_ids=tuple(str(item) for item in metadata.get("fact_ids", ())),
            metadata=dict(metadata.get("metadata") or {}),
        )


def _dynamic_execution(run: MissionRun, proposal_id: str) -> StepExecution | None:
    return next(
        (
            execution
            for execution in run.steps
            if bool(execution.metadata.get("dynamic"))
            and str(execution.metadata.get("proposal_id") or "") == proposal_id
        ),
        None,
    )


def classify_proposal_outcome(run: MissionRun, proposal: Any, accepted: bool) -> ActionOutcome:
    """Classify one proposal from persisted runtime state after an execution attempt."""
    action_id = f"dynamic:{proposal.id}"
    execution = _dynamic_execution(run, proposal.id)
    proposal_node = run.graph.nodes.get(proposal.id)
    proposal_status = str(proposal_node.metadata.get("status") or "") if proposal_node else ""

    if proposal_status == "denied_scope":
        return ActionOutcome.create(
            action_id=action_id,
            proposal_id=proposal.id,
            kind=ActionOutcomeKind.OUT_OF_SCOPE,
            summary=str(proposal_node.metadata.get("error") or "proposal target is outside authorized scope"),
            tool=proposal.tool,
            target=proposal.target,
        )

    if execution is None:
        if accepted and run.state.value == "waiting_approval":
            return ActionOutcome.create(
                action_id=action_id,
                proposal_id=proposal.id,
                kind=ActionOutcomeKind.APPROVAL_REQUIRED,
                summary="explicit approval grant required",
                tool=proposal.tool,
                target=proposal.target,
            )
        return ActionOutcome.create(
            action_id=action_id,
            proposal_id=proposal.id,
            kind=ActionOutcomeKind.TECHNICAL_FAILURE,
            summary="proposal was not materialized into an executable action",
            tool=proposal.tool,
            target=proposal.target,
            metadata={"accepted": bool(accepted)},
        )

    preflight = execution.metadata.get("preflight")
    error = str(execution.error or "")
    if execution.state is StepExecutionState.WAITING_APPROVAL:
        kind = ActionOutcomeKind.APPROVAL_REQUIRED
    elif execution.state is StepExecutionState.DENIED:
        kind = ActionOutcomeKind.POLICY_DENIED
    elif execution.state is StepExecutionState.DEGRADED:
        kind = ActionOutcomeKind.DEGRADED
    elif execution.state is StepExecutionState.FAILED and error.startswith("unknown tool:"):
        kind = ActionOutcomeKind.TOOL_UNAVAILABLE
    elif execution.state is StepExecutionState.FAILED and isinstance(preflight, dict) and preflight.get("ready") is False:
        kind = ActionOutcomeKind.TOOL_UNAVAILABLE
    elif execution.state is StepExecutionState.FAILED:
        kind = ActionOutcomeKind.TECHNICAL_FAILURE
    elif execution.state is StepExecutionState.SUCCEEDED:
        fact_ids = tuple(str(item) for item in execution.metadata.get("fact_ids", ()))
        kind = ActionOutcomeKind.SUCCESS if fact_ids else ActionOutcomeKind.INSUFFICIENT_EVIDENCE
    else:
        kind = ActionOutcomeKind.TECHNICAL_FAILURE

    fact_ids = tuple(str(item) for item in execution.metadata.get("fact_ids", ()))
    return ActionOutcome.create(
        action_id=execution.id,
        proposal_id=proposal.id,
        kind=kind,
        summary=execution.error or kind.value.replace("_", " "),
        tool=execution.tool,
        target=execution.target,
        evidence_id=execution.evidence_id,
        fact_ids=fact_ids,
        metadata={"state": execution.state.value, "accepted": bool(accepted)},
    )


def record_action_outcome(run: MissionRun, outcome: ActionOutcome) -> ActionOutcome:
    """Persist a structured outcome in both the action record and provenance graph."""
    execution = next((entry for entry in run.steps if entry.id == outcome.action_id), None)
    if execution is not None:
        execution.metadata["action_outcome"] = outcome.as_dict()

    if outcome.id not in run.graph.nodes:
        run.graph.add_node(
            GraphNode(
                id=outcome.id,
                kind="action.outcome",
                label=outcome.summary,
                metadata={
                    "action_id": outcome.action_id,
                    "kind": outcome.kind.value,
                    "tool": outcome.tool,
                    "target": outcome.target,
                    "proposal_id": outcome.proposal_id,
                    "evidence_id": outcome.evidence_id,
                    "fact_ids": list(outcome.fact_ids),
                    "environmental": outcome.environmental,
                    "evidence_bearing": outcome.evidence_bearing,
                    "may_revise_belief": outcome.may_revise_belief,
                    "metadata": dict(outcome.metadata),
                },
            )
        )
        run.graph.link(run.id, "recorded_outcome", outcome.id)
        if outcome.action_id in run.graph.nodes:
            run.graph.link(outcome.action_id, "resulted_in", outcome.id)
        if outcome.proposal_id and outcome.proposal_id in run.graph.nodes:
            run.graph.link(outcome.proposal_id, "resulted_in", outcome.id)
        if outcome.evidence_id and outcome.evidence_id in run.graph.nodes:
            run.graph.link(outcome.evidence_id, "supports_outcome", outcome.id)
    return outcome
