from .arsenal import (
    ArsenalPortscanAdapter,
    ArsenalSqliAdapter,
    ArsenalWafAdapter,
    SqlmapAdapter,
)
from .httpx import HttpxAdapter
from .katana import KatanaAdapter
from .nmap import NmapAdapter
from .nuclei import NucleiAdapter
from .subfinder import SubfinderAdapter


def register_builtin_adapters(registry) -> None:
    registry.register(NmapAdapter())
    registry.register(HttpxAdapter())
    registry.register(NucleiAdapter())
    registry.register(KatanaAdapter())
    registry.register(SubfinderAdapter())
    registry.register(ArsenalPortscanAdapter())
    registry.register(ArsenalSqliAdapter())
    registry.register(ArsenalWafAdapter())
    registry.register(SqlmapAdapter())


__all__ = [
    "ArsenalPortscanAdapter",
    "ArsenalSqliAdapter",
    "ArsenalWafAdapter",
    "HttpxAdapter",
    "KatanaAdapter",
    "NmapAdapter",
    "NucleiAdapter",
    "SqlmapAdapter",
    "SubfinderAdapter",
    "register_builtin_adapters",
]
