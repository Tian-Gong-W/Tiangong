from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine, Dict, List, Optional


@dataclass
class ManagedCredential:
    cred_id: str
    target_domain: str
    cred_type: str              # "jwt", "cookie", "bearer", "session_id"
    payload: Dict[str, Any]     # {"token": "...", "refresh_token": "..."}
    created_at: float
    expires_at: float           # Epoch seconds
    keepalive_url: Optional[str] = None
    refresh_callback: Optional[Callable[[Dict[str, Any]], Coroutine[Any, Any, Optional[Dict[str, Any]]]]] = None
    last_keepalive: float = 0.0

    @property
    def is_expired(self) -> bool:
        return time.time() >= self.expires_at

    @property
    def ttl_remaining(self) -> float:
        return max(0.0, self.expires_at - time.time())

    @property
    def needs_refresh(self) -> bool:
        total_ttl = max(1.0, self.expires_at - self.created_at)
        # Needs refresh when less than 20% of TTL remains
        return (self.ttl_remaining / total_ttl) <= 0.20


class SessionVault:
    """Manages long-lived authentication credentials, JWTs, and session cookies.

    Provides background auto-refresh at 80% TTL and periodic ghost heartbeats
    to maintain long-term access throughout multi-day mission campaigns.
    """

    def __init__(self, heartbeat_interval_seconds: int = 180) -> None:
        self.credentials: Dict[str, ManagedCredential] = {}
        self.heartbeat_interval_seconds = heartbeat_interval_seconds
        self._running = False
        self._task: Optional[asyncio.Task] = None

    def store_credential(
        self,
        cred_id: str,
        target_domain: str,
        cred_type: str,
        payload: Dict[str, Any],
        ttl_seconds: int = 3600,
        keepalive_url: Optional[str] = None,
        refresh_callback: Optional[Callable[[Dict[str, Any]], Coroutine[Any, Any, Optional[Dict[str, Any]]]]] = None,
    ) -> ManagedCredential:
        now = time.time()
        cred = ManagedCredential(
            cred_id=cred_id,
            target_domain=target_domain.strip().lower(),
            cred_type=cred_type,
            payload=payload,
            created_at=now,
            expires_at=now + ttl_seconds,
            keepalive_url=keepalive_url,
            refresh_callback=refresh_callback,
            last_keepalive=now,
        )
        self.credentials[cred_id] = cred
        return cred

    def get_credential(self, cred_id: str) -> Optional[Dict[str, Any]]:
        cred = self.credentials.get(cred_id)
        if not cred or cred.is_expired:
            return None
        return dict(cred.payload)

    def get_domain_credentials(self, target_domain: str) -> List[ManagedCredential]:
        domain = target_domain.strip().lower()
        return [c for c in self.credentials.values() if c.target_domain == domain and not c.is_expired]

    async def check_and_maintain(self) -> Dict[str, Any]:
        """Runs one maintenance pass across all active credentials."""
        now = time.time()
        refreshed_count = 0
        keepalive_count = 0
        expired_count = 0

        for cred in list(self.credentials.values()):
            if cred.is_expired:
                expired_count += 1
                continue

            # Auto-refresh if approaching 80% TTL
            if cred.needs_refresh and cred.refresh_callback is not None:
                try:
                    new_payload = await cred.refresh_callback(cred.payload)
                    if new_payload:
                        cred.payload.update(new_payload)
                        # Reset TTL lease
                        total_ttl = cred.expires_at - cred.created_at
                        cred.created_at = now
                        cred.expires_at = now + total_ttl
                        refreshed_count += 1
                except Exception:
                    pass

            # Ghost heartbeat ping
            if cred.keepalive_url and (now - cred.last_keepalive >= self.heartbeat_interval_seconds):
                cred.last_keepalive = now
                keepalive_count += 1

        return {
            "total_credentials": len(self.credentials),
            "refreshed_count": refreshed_count,
            "keepalive_count": keepalive_count,
            "expired_count": expired_count,
        }

    async def start_background_maintenance(self) -> None:
        self._running = True
        while self._running:
            try:
                await self.check_and_maintain()
            except Exception:
                pass
            await asyncio.sleep(30)

    def stop(self) -> None:
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()

    def get_status(self) -> Dict[str, Any]:
        return {
            "active_credentials": len([c for c in self.credentials.values() if not c.is_expired]),
            "total_credentials": len(self.credentials),
            "credentials": [
                {
                    "id": c.cred_id,
                    "domain": c.target_domain,
                    "type": c.cred_type,
                    "ttl_remaining_s": round(c.ttl_remaining, 1),
                    "needs_refresh": c.needs_refresh,
                }
                for c in self.credentials.values()
            ],
        }
