from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping
from uuid import uuid4


class FactKind(str, Enum):
    HOST = "host"
    SERVICE = "service"
    DNS = "dns"
    TLS = "tls"
    WEB = "web"
    FINDING = "finding"


class Severity(str, Enum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class IntelligenceFact:
    id: str
    kind: FactKind
    source: str
    target: str | None
    title: str
    evidence_id: str
    confidence: float
    severity: Severity = Severity.INFO
    data: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        *,
        kind: FactKind,
        source: str,
        target: str | None,
        title: str,
        evidence_id: str,
        confidence: float = 1.0,
        severity: Severity = Severity.INFO,
        data: Mapping[str, Any] | None = None,
    ) -> "IntelligenceFact":
        if not 0.0 <= confidence <= 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")
        return cls(
            id=uuid4().hex,
            kind=kind,
            source=source,
            target=target,
            title=title,
            evidence_id=evidence_id,
            confidence=confidence,
            severity=severity,
            data=dict(data or {}),
        )
