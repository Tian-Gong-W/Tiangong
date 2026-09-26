from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping
from uuid import uuid4


@dataclass(frozen=True, slots=True)
class Observation:
    id: str
    source: str
    target: str | None
    summary: str
    evidence_id: str | None
    captured_at: datetime
    metadata: Mapping[str, Any]

    @classmethod
    def create(
        cls,
        *,
        source: str,
        target: str | None,
        summary: str,
        evidence_id: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> "Observation":
        return cls(
            id=uuid4().hex,
            source=source,
            target=target,
            summary=summary,
            evidence_id=evidence_id,
            captured_at=datetime.now(timezone.utc),
            metadata=dict(metadata or {}),
        )
