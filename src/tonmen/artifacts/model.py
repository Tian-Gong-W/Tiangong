from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class ArtifactReport:
    """Static, non-executing identity and binary-format observations."""

    sha256: str
    size: int
    source_name: str
    format: str
    architecture: str | None
    bitness: int | None
    endianness: str | None
    mitigations: Mapping[str, bool | None] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()
    inspected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["mitigations"] = dict(self.mitigations)
        payload["metadata"] = dict(self.metadata)
        payload["warnings"] = list(self.warnings)
        payload["inspected_at"] = self.inspected_at.isoformat()
        payload["execution_performed"] = False
        return payload
