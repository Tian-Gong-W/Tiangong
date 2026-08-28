from __future__ import annotations

import os

from .httpx import HttpxAdapter
from .katana import KatanaAdapter
from .nmap import NmapAdapter
from .nuclei import NucleiAdapter
from .subfinder import SubfinderAdapter


def extended_discovery_enabled() -> bool:
    return (os.getenv("TONMEN_EXTENDED_DISCOVERY") or "").strip().lower() in {"1", "true", "yes", "on"}


def register_builtin_adapters(registry) -> None:
    """Register the stable governed core plus optional evidence-expansion adapters.

    Nmap / httpx / nuclei remain the compatibility baseline. Subfinder and Katana
    expand the Director's evidence-gathering capability library when explicitly
    enabled, but their presence must not silently redefine every frozen MissionPlan.
    """
    registry.register(NmapAdapter())
    registry.register(HttpxAdapter())
    registry.register(NucleiAdapter())
    if extended_discovery_enabled():
        registry.register(SubfinderAdapter())
        registry.register(KatanaAdapter())


__all__ = [
    "HttpxAdapter",
    "KatanaAdapter",
    "NmapAdapter",
    "NucleiAdapter",
    "SubfinderAdapter",
    "extended_discovery_enabled",
    "register_builtin_adapters",
]
