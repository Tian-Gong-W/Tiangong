from .httpx import HttpxAdapter
from .katana import KatanaAdapter
from .nmap import NmapAdapter
from .nuclei import NucleiAdapter
from .subfinder import SubfinderAdapter


def register_builtin_adapters(registry) -> None:
    registry.register(NmapAdapter())
    registry.register(SubfinderAdapter())
    registry.register(HttpxAdapter())
    registry.register(KatanaAdapter())
    registry.register(NucleiAdapter())


__all__ = [
    "HttpxAdapter",
    "KatanaAdapter",
    "NmapAdapter",
    "NucleiAdapter",
    "SubfinderAdapter",
    "register_builtin_adapters",
]
