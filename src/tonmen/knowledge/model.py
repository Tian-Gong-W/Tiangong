from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from math import pow
from typing import Any, Mapping
from uuid import uuid4


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def parse_datetime(value: str | datetime | None, *, default: datetime | None = None) -> datetime:
    if isinstance(value, datetime):
        return ensure_utc(value)
    text = str(value or "").strip()
    if text:
        if text.endswith("Z"):
            text = f"{text[:-1]}+00:00"
        return ensure_utc(datetime.fromisoformat(text))
    return ensure_utc(default or utcnow())


def normalize_values(values) -> tuple[str, ...]:
    ordered: list[str] = []
    seen: set[str] = set()
    for value in values or ():
        text = str(value or "").strip()
        if not text:
            continue
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(text)
    return tuple(ordered)


class KnowledgeKind(str, Enum):
    MARKET_PATTERN = "market_pattern"
    DEFENSE_PATTERN = "defense_pattern"
    THREAT_PATTERN = "threat_pattern"
    TECHNIQUE = "technique"
    TOOL_CAPABILITY = "tool_capability"
    PRODUCT_CHANGE = "product_change"


class FreshnessState(str, Enum):
    CURRENT = "current"
    AGING = "aging"
    STALE = "stale"


@dataclass(frozen=True, slots=True)
class KnowledgeRecord:
    """Time-bounded knowledge claim used to form research hypotheses.

    A record is not evidence about a target. It may influence what evidence is
    worth seeking, but it cannot create a Finding on its own.
    """

    id: str
    kind: KnowledgeKind
    title: str
    summary: str
    source: str
    source_url: str | None
    published_at: datetime
    retrieved_at: datetime
    confidence: float = 0.8
    source_trust: float = 0.8
    max_age_days: int = 90
    technologies: tuple[str, ...] = ()
    industries: tuple[str, ...] = ()
    organization_scales: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    required_products: tuple[str, ...] = ()
    preferred_modalities: tuple[str, ...] = ()
    prerequisites: tuple[str, ...] = ()
    state_changes: tuple[str, ...] = ()
    technique_id: str | None = None
    enables: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        *,
        kind: KnowledgeKind | str,
        title: str,
        summary: str,
        source: str,
        source_url: str | None = None,
        published_at: datetime | str | None = None,
        retrieved_at: datetime | str | None = None,
        confidence: float = 0.8,
        source_trust: float = 0.8,
        max_age_days: int = 90,
        technologies=(),
        industries=(),
        organization_scales=(),
        tags=(),
        required_products=(),
        preferred_modalities=(),
        prerequisites=(),
        state_changes=(),
        technique_id: str | None = None,
        enables=(),
        metadata: Mapping[str, Any] | None = None,
        record_id: str | None = None,
    ) -> "KnowledgeRecord":
        resolved_kind = kind if isinstance(kind, KnowledgeKind) else KnowledgeKind(str(kind))
        published = parse_datetime(published_at)
        retrieved = parse_datetime(retrieved_at, default=published)
        return cls(
            id=str(record_id or uuid4().hex),
            kind=resolved_kind,
            title=str(title).strip(),
            summary=str(summary).strip(),
            source=str(source).strip(),
            source_url=str(source_url).strip() if source_url else None,
            published_at=published,
            retrieved_at=retrieved,
            confidence=max(0.0, min(1.0, float(confidence))),
            source_trust=max(0.0, min(1.0, float(source_trust))),
            max_age_days=max(1, int(max_age_days)),
            technologies=normalize_values(technologies),
            industries=normalize_values(industries),
            organization_scales=normalize_values(organization_scales),
            tags=normalize_values(tags),
            required_products=normalize_values(required_products),
            preferred_modalities=normalize_values(preferred_modalities),
            prerequisites=normalize_values(prerequisites),
            state_changes=normalize_values(state_changes),
            technique_id=str(technique_id).strip() if technique_id else None,
            enables=normalize_values(enables),
            metadata=dict(metadata or {}),
        )

    @property
    def freshness_anchor(self) -> datetime:
        # Publication recency matters more than when an old record was re-fetched.
        return self.published_at

    def age_days(self, *, now: datetime | None = None) -> float:
        current = ensure_utc(now or utcnow())
        delta = current - ensure_utc(self.freshness_anchor)
        return max(0.0, delta.total_seconds() / 86400.0)

    def freshness_state(self, *, now: datetime | None = None) -> FreshnessState:
        age = self.age_days(now=now)
        if age > self.max_age_days:
            return FreshnessState.STALE
        if age > self.max_age_days * 0.4:
            return FreshnessState.AGING
        return FreshnessState.CURRENT

    def freshness_score(self, *, now: datetime | None = None) -> float:
        age = self.age_days(now=now)
        if age > self.max_age_days:
            return 0.0
        half_life = max(1.0, self.max_age_days / 2.0)
        return max(0.0, min(1.0, pow(2.0, -(age / half_life))))

    def effective_weight(self, *, now: datetime | None = None) -> float:
        return self.confidence * self.source_trust * self.freshness_score(now=now)

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind.value,
            "title": self.title,
            "summary": self.summary,
            "source": self.source,
            "source_url": self.source_url,
            "published_at": self.published_at.isoformat(),
            "retrieved_at": self.retrieved_at.isoformat(),
            "confidence": self.confidence,
            "source_trust": self.source_trust,
            "max_age_days": self.max_age_days,
            "technologies": list(self.technologies),
            "industries": list(self.industries),
            "organization_scales": list(self.organization_scales),
            "tags": list(self.tags),
            "required_products": list(self.required_products),
            "preferred_modalities": list(self.preferred_modalities),
            "prerequisites": list(self.prerequisites),
            "state_changes": list(self.state_changes),
            "technique_id": self.technique_id,
            "enables": list(self.enables),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "KnowledgeRecord":
        return cls.create(
            record_id=str(data.get("id") or uuid4().hex),
            kind=str(data["kind"]),
            title=str(data.get("title") or ""),
            summary=str(data.get("summary") or ""),
            source=str(data.get("source") or ""),
            source_url=data.get("source_url"),
            published_at=data.get("published_at"),
            retrieved_at=data.get("retrieved_at"),
            confidence=float(data.get("confidence", 0.8)),
            source_trust=float(data.get("source_trust", 0.8)),
            max_age_days=int(data.get("max_age_days", 90)),
            technologies=data.get("technologies", ()),
            industries=data.get("industries", ()),
            organization_scales=data.get("organization_scales", ()),
            tags=data.get("tags", ()),
            required_products=data.get("required_products", ()),
            preferred_modalities=data.get("preferred_modalities", ()),
            prerequisites=data.get("prerequisites", ()),
            state_changes=data.get("state_changes", ()),
            technique_id=data.get("technique_id"),
            enables=data.get("enables", ()),
            metadata=data.get("metadata") if isinstance(data.get("metadata"), Mapping) else {},
        )
