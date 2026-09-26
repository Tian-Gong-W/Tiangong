from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping
from uuid import uuid4


class ReasoningAction(str, Enum):
    CONTINUE = "continue"
    REQUEST_APPROVAL = "request_approval"
    SKIP = "skip"
    REVIEW = "review"
    COMPLETE = "complete"
    NO_ACTION = "no_executable_action"
    STOP = "stop"
    # Phase 1: allow the reasoner to emit brand-new work instead of only
    # selecting among the original frozen plan steps.
    PROPOSE = "propose"


class HypothesisStatus(str, Enum):
    OPEN = "open"
    SUPPORTED = "supported"
    CONTRADICTED = "contradicted"
    ABANDONED = "abandoned"


@dataclass(frozen=True, slots=True)
class Hypothesis:
    """A live research hypothesis the runtime can support, contradict or abandon."""

    id: str
    statement: str
    confidence: float
    supporting_fact_ids: tuple[str, ...] = ()
    contradicting_fact_ids: tuple[str, ...] = ()
    status: HypothesisStatus = HypothesisStatus.OPEN
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        *,
        statement: str,
        confidence: float = 0.5,
        supporting_fact_ids: tuple[str, ...] = (),
        contradicting_fact_ids: tuple[str, ...] = (),
        status: HypothesisStatus = HypothesisStatus.OPEN,
        metadata: Mapping[str, Any] | None = None,
    ) -> "Hypothesis":
        return cls(
            id=uuid4().hex,
            statement=statement,
            confidence=max(0.0, min(1.0, confidence)),
            supporting_fact_ids=tuple(supporting_fact_ids),
            contradicting_fact_ids=tuple(contradicting_fact_ids),
            status=status,
            metadata=dict(metadata or {}),
        )


@dataclass(frozen=True, slots=True)
class ActionProposal:
    """A late-bound action the runtime may schedule after the original plan was created.

    Every proposal must still pass Scope, risk and approval checks before execution.
    """

    id: str
    tool: str
    target: str
    parameters: Mapping[str, Any]
    rationale: str
    expected_info_gain: float
    risk: int
    requires_approval: bool
    hypothesis_id: str | None = None
    estimated_cost: int = 1
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        *,
        tool: str,
        target: str,
        parameters: Mapping[str, Any] | None = None,
        rationale: str,
        expected_info_gain: float = 0.5,
        risk: int = 1,
        requires_approval: bool = False,
        hypothesis_id: str | None = None,
        estimated_cost: int = 1,
        metadata: Mapping[str, Any] | None = None,
    ) -> "ActionProposal":
        return cls(
            id=uuid4().hex,
            tool=tool,
            target=target,
            parameters=dict(parameters or {}),
            rationale=rationale,
            expected_info_gain=max(0.0, min(1.0, expected_info_gain)),
            risk=int(risk),
            requires_approval=bool(requires_approval),
            hypothesis_id=hypothesis_id,
            estimated_cost=max(1, int(estimated_cost)),
            metadata=dict(metadata or {}),
        )


@dataclass(frozen=True, slots=True)
class ReasoningDecision:
    id: str
    action: ReasoningAction
    summary: str
    basis_fact_ids: tuple[str, ...] = ()
    next_step_id: str | None = None
    requires_human: bool = False
    # Phase 1 extension: the reasoner may emit zero or more new proposals
    # instead of (or in addition to) selecting an existing plan step.
    new_proposals: tuple[ActionProposal, ...] = ()
    hypotheses: tuple[Hypothesis, ...] = ()

    @classmethod
    def create(
        cls,
        *,
        action: ReasoningAction,
        summary: str,
        basis_fact_ids: tuple[str, ...] = (),
        next_step_id: str | None = None,
        requires_human: bool = False,
        new_proposals: tuple[ActionProposal, ...] | list[ActionProposal] = (),
        hypotheses: tuple[Hypothesis, ...] | list[Hypothesis] = (),
    ) -> "ReasoningDecision":
        return cls(
            id=uuid4().hex,
            action=action,
            summary=summary,
            basis_fact_ids=tuple(basis_fact_ids),
            next_step_id=next_step_id,
            requires_human=requires_human,
            new_proposals=tuple(new_proposals),
            hypotheses=tuple(hypotheses),
        )
