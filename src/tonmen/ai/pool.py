from __future__ import annotations

import os

from .hub import ProviderHub as _ProviderHub


class ProviderHub(_ProviderHub):
    """Provider pool that never infers subagent routing from Lead AI settings.

    Multi-provider subagent calls require the explicit TONMEN_AI_POOL variable so
    enabling a Lead model cannot unexpectedly multiply network calls or cost.
    """

    def __init__(self, pool: tuple[str, ...] | None = None) -> None:
        if pool is None:
            values: list[str] = []
            for item in (os.getenv("TONMEN_AI_POOL") or "").split(","):
                provider_id = item.strip().lower()
                if not provider_id or provider_id in values:
                    continue
                try:
                    self.spec(provider_id)
                except ValueError:
                    continue
                values.append(provider_id)
            pool = tuple(values)
        super().__init__(pool=pool)
