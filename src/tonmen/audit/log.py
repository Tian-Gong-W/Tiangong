from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


@dataclass(frozen=True, slots=True)
class AuditEvent:
    id: str
    timestamp: datetime
    action: str
    tool: str
    target: str | None
    decision: str
    message: str
    evidence_id: str | None = None


class AuditLog:
    """Append-only JSONL audit log. Raw scanner output lives in evidence, not audit."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def append(
        self,
        *,
        action: str,
        tool: str,
        target: str | None,
        decision: str,
        message: str,
        evidence_id: str | None = None,
    ) -> AuditEvent:
        event = AuditEvent(
            id=uuid4().hex,
            timestamp=datetime.now(timezone.utc),
            action=action,
            tool=tool,
            target=target,
            decision=decision,
            message=message,
            evidence_id=evidence_id,
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = asdict(event)
        payload["timestamp"] = event.timestamp.isoformat()
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
        return event
