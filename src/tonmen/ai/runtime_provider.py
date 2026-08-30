from __future__ import annotations

import os
import threading
from time import monotonic
from typing import Any

from .pool import ProviderHub as BaseProviderHub


_FALSE = {"0", "false", "no", "off"}


def _enabled(name: str, default: bool = False) -> bool:
    raw = (os.getenv(name) or "").strip().lower()
    if not raw:
        return default
    return raw not in _FALSE


class ProviderHub(BaseProviderHub):
    """Production ProviderHub with authenticated readiness semantics.

    Installing a browser-login CLI is not enough to make it routable. Candidate
    construction remains side-effect free; real authentication is checked only when
    the provider is selected or explicitly probed. Google Antigravity is kept
    authentication-capable but excluded from Council routing by default because its
    current headless permission boundary is not accepted as a hard TONMEN boundary.
    Operators may explicitly opt in after validation with
    TONMEN_ANTIGRAVITY_HEADLESS_ALLOWED=1.
    """

    _probe_cache: dict[str, tuple[float, dict[str, Any]]] = {}
    _cache_lock = threading.Lock()
    _cache_ttl_seconds = 5.0

    @classmethod
    def invalidate_probe(cls, provider_id: str | None = None) -> None:
        with cls._cache_lock:
            if provider_id is None:
                cls._probe_cache.clear()
            else:
                cls._probe_cache.pop(str(provider_id).strip().lower(), None)

    @staticmethod
    def _runtime_blocker(provider_id: str, authenticated: bool) -> str | None:
        if not authenticated:
            return "provider authentication has not been confirmed"
        if provider_id == "google" and not _enabled("TONMEN_ANTIGRAVITY_HEADLESS_ALLOWED", False):
            return (
                "Antigravity authentication is valid, but headless Council routing is disabled until "
                "its permission boundary is explicitly accepted by the operator"
            )
        return None

    def probe(self, provider_id: str, *, timeout: int = 8) -> dict[str, Any]:
        provider_id = str(provider_id).strip().lower()
        now = monotonic()
        with self._cache_lock:
            cached = self._probe_cache.get(provider_id)
            if cached and now - cached[0] < self._cache_ttl_seconds:
                return dict(cached[1])

        raw = dict(super().probe(provider_id, timeout=timeout))
        spec = self.spec(provider_id)
        authenticated = bool(raw.get("ready"))
        blocker = self._runtime_blocker(provider_id, authenticated)
        runtime_ready = authenticated and blocker is None
        detail = str(raw.get("detail") or "")[:240]
        if blocker:
            detail = f"{detail}; {blocker}" if detail else blocker
        result = {
            **raw,
            "auth_mode": spec.auth_mode,
            "installed": self._installed(spec) if spec.executable else None,
            "authenticated": authenticated,
            "runtime_ready": runtime_ready,
            "runtime_blocker": blocker,
            "ready": runtime_ready,
            "detail": detail[:500],
        }
        with self._cache_lock:
            self._probe_cache[provider_id] = (now, dict(result))
        return result

    def authentication_status(self, provider_id: str, *, timeout: int = 3) -> dict[str, Any]:
        # Keep this compatibility-friendly for callers/tests that replace `probe`
        # with the historic `(provider_id)` signature. Production callers that need
        # a specific timeout invoke `probe(..., timeout=...)` directly.
        return self.probe(provider_id)

    def is_ready(self, provider_id: str) -> bool:
        return bool(self.authentication_status(provider_id).get("runtime_ready"))
