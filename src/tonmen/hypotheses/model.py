from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from uuid import uuid4


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

    def __post_init__(self) -> None:
        if self.minimum_independent_sources < 1:
            raise ValueError("minimum_independent_sources must be at least 1")


@dataclass(frozen=True, slots=True)
class Hypothesis:
    id: str
    statement: str
    status: HypothesisStatus
    scope_entities: tuple[str, ...]
    evidence_requirements: tuple[EvidenceRequirement, ...]
    supporting_evidence_ids: tuple[str, ...] = ()
    contradicting_evidence_ids: tuple[str, ...] = ()
    confidence: float = 0.5
    relevance: float = 1.0
    impact_prior: float = 0.5
    created_by: str = "planner"

    def __post_init__(self) -> None:
        for name, value in (
            ("confidence", self.confidence),
            ("relevance", self.relevance),
            ("impact_prior", self.impact_prior),
        ):
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be between 0 and 1")

    @classmethod
    def create(
        cls,
        statement: str,
        *,
        scope_entities: tuple[str, ...],
        evidence_requirements: tuple[EvidenceRequirement, ...],
        status: HypothesisStatus = HypothesisStatus.OPEN,
        confidence: float = 0.5,
        relevance: float = 1.0,
        impact_prior: float = 0.5,
        created_by: str = "planner",
    ) -> "Hypothesis":
        return cls(
            id=uuid4().hex,
            statement=statement,
            status=status,
            scope_entities=scope_entities,
            evidence_requirements=evidence_requirements,
            confidence=confidence,
            relevance=relevance,
            impact_prior=impact_prior,
            created_by=created_by,
        )
