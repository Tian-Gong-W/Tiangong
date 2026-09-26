from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class EvidenceRecord:
    id: str
    tool: str
    target: str | None
    argv: tuple[str, ...]
    exit_code: int
    stdout: str
    stderr: str
    started_at: datetime
    finished_at: datetime
