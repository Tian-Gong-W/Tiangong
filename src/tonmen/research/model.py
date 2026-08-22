from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping
from uuid import uuid4

from tonmen.tools import CostEstimate, RiskLevel


class HypothesisStatus(str, Enum):
    OPEN = "open"
    SUPPORTED = "supported"
    REJECTED = "rejected"
    CONFIRMED = "confirmed"


@dataclass(frozen=True, slots=True)
class EvidenceRequirement:
    description: str
    required_modalities: tuple[str, ...] = ()
    minimum_independent_sources: int = 1
    requires_replay: bool = False


@dataclass(slots=True)
class Hypothesis:
    id: str
    statement: str
    status: HypothesisStatus = HypothesisStatus.OPEN
    evidence_requirements: tuple[EvidenceRequirement, ...] = ()
    supporting_evidence_ids: list[str] = field(default_factory=list)
    contradicting_evidence_ids: list[str] = field(default_factory=list)
    confidence: float = 0.5
    relevance: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        statement: str,
        *,
        evidence_requirements: tuple[EvidenceRequirement, ...] = (),
        relevance: float = 1.0,
        metadata: Mapping[str, Any] | None = None,
    ) -> "Hypothesis":
        return cls(
            id=uuid4().hex,
            statement=statement,
            evidence_requirements=evidence_requirements,
            relevance=float(relevance),
            metadata=dict(metadata or {}),
        )


@dataclass(frozen=True, slots=True)
class ActionProposal:
    id: str
    capability: str
    target: str | None
    parameters: Mapping[str, Any]
    hypothesis_ids: tuple[str, ...]
    expected_information_gain: float
    relevance: float
    estimated_cost: CostEstimate
    risk: RiskLevel
    replayable: bool
    requires_approval: bool
    rationale: str

    @classmethod
    def create(
        cls,
        *,
        capability: str,
        target: str | None,
        parameters: Mapping[str, Any] | None = None,
        hypothesis_ids: tuple[str, ...] = (),
        expected_information_gain: float = 0.5,
        relevance: float = 1.0,
        estimated_cost: CostEstimate | None = None,
        risk: RiskLevel = RiskLevel.DISCOVERY,
        replayable: bool = True,
        requires_approval: bool = False,
        rationale: str,
    ) -> "ActionProposal":
        return cls(
            id=uuid4().hex,
            capability=capability,
            target=target,
            parameters=dict(parameters or {}),
            hypothesis_ids=tuple(hypothesis_ids),
            expected_information_gain=max(0.0, float(expected_information_gain)),
            relevance=max(0.0, float(relevance)),
            estimated_cost=estimated_cost or CostEstimate(),
            risk=risk,
            replayable=bool(replayable),
            requires_approval=bool(requires_approval),
            rationale=rationale,
        )

    @property
    def utility(self) -> float:
        return (self.expected_information_gain * self.relevance) / self.estimated_cost.effective_cost

    @property
    def signature(self) -> tuple[object, ...]:
        normalized_parameters = tuple(sorted((str(key), repr(value)) for key, value in self.parameters.items()))
        return (self.capability, self.target, normalized_parameters)


class ActionState(str, Enum):
    PROPOSED = "proposed"
    WAITING_APPROVAL = "waiting_approval"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    DENIED = "denied"
    SKIPPED = "skipped"


@dataclass(slots=True)
class ActionRecord:
    proposal: ActionProposal
    state: ActionState = ActionState.PROPOSED
    evidence_id: str | None = None
    job_id: str | None = None
    error: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: datetime | None = None

    @property
    def signature(self) -> tuple[object, ...]:
        return self.proposal.signature


@dataclass(slots=True)
class AdaptiveMissionState:
    mission_id: str
    target: str
    hypotheses: dict[str, Hypothesis]
    action_ledger: list[ActionRecord] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    converged: bool = False

    @classmethod
    def create(
        cls,
        target: str,
        hypotheses: tuple[Hypothesis, ...],
        *,
        metadata: Mapping[str, Any] | None = None,
    ) -> "AdaptiveMissionState":
        return cls(
            mission_id=uuid4().hex,
            target=target,
            hypotheses={item.id: item for item in hypotheses},
            metadata=dict(metadata or {}),
        )

    @property
    def attempted_signatures(self) -> set[tuple[object, ...]]:
        return {record.signature for record in self.action_ledger}


@dataclass(frozen=True, slots=True)
class BootstrapResult:
    initial_hypotheses: tuple[Hypothesis, ...]
    initial_actions: tuple[ActionProposal, ...]
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class PlannerDecision:
    candidates: tuple[ActionProposal, ...]
    explanation: str

    @property
    def best(self) -> ActionProposal | None:
        if not self.candidates:
            return None
        return max(self.candidates, key=lambda item: item.utility)
