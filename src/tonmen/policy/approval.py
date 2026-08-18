from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from secrets import token_urlsafe

from tonmen.tools import ToolRequest


@dataclass(frozen=True, slots=True)
class ApprovalGrant:
    token: str
    tool: str
    target: str
    issued_at: datetime
    expires_at: datetime


class ApprovalStore:
    """In-memory, single-use grants bound to one tool and one target."""

    def __init__(self) -> None:
        self._grants: dict[str, ApprovalGrant] = {}

    def issue(self, *, tool: str, target: str, ttl_seconds: int = 600) -> ApprovalGrant:
        if ttl_seconds < 1 or ttl_seconds > 3600:
            raise ValueError("approval ttl must be between 1 and 3600 seconds")
        now = datetime.now(timezone.utc)
        grant = ApprovalGrant(
            token=token_urlsafe(24),
            tool=tool.strip().lower(),
            target=target,
            issued_at=now,
            expires_at=now + timedelta(seconds=ttl_seconds),
        )
        self._grants[grant.token] = grant
        return grant

    def revoke(self, token: str) -> bool:
        """Remove an unconsumed grant without exposing its contents."""
        return self._grants.pop(token, None) is not None

    def validate(self, token: str, request: ToolRequest) -> ApprovalGrant | None:
        """Check a grant without consuming it so preflight failures do not burn approval."""
        grant = self._grants.get(token)
        if grant is None:
            return None
        now = datetime.now(timezone.utc)
        if grant.expires_at <= now:
            return None
        if grant.tool != request.tool.strip().lower() or grant.target != request.target:
            return None
        return grant

    def consume(self, token: str, request: ToolRequest) -> ApprovalGrant | None:
        grant = self.validate(token, request)
        if grant is None:
            return None
        self._grants.pop(token, None)
        return grant
