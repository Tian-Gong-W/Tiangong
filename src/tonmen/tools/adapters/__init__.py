from .crawler import CrawlerAdapter
from .httpx import HttpxAdapter
from .nmap import NmapAdapter
from .nuclei import NucleiAdapter


def register_builtin_adapters(registry) -> None:
    registry.register(NmapAdapter())
    registry.register(HttpxAdapter())
    registry.register(CrawlerAdapter())
    registry.register(NucleiAdapter())


__all__ = [
    "CrawlerAdapter",
    "HttpxAdapter",
    "NmapAdapter",
    "NucleiAdapter",
    "register_builtin_adapters",
]
