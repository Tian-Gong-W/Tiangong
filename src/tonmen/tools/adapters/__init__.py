from .api_intel import ApiIntelAdapter
from .crawler import CrawlerAdapter
from .dns_intel import DnsIntelAdapter
from .httpx import HttpxAdapter
from .nmap import NmapAdapter
from .nuclei import NucleiAdapter
from .tls_intel import TlsIntelAdapter


def register_builtin_adapters(registry) -> None:
    registry.register(NmapAdapter())
    registry.register(DnsIntelAdapter())
    registry.register(HttpxAdapter())
    registry.register(TlsIntelAdapter())
    registry.register(ApiIntelAdapter())
    registry.register(CrawlerAdapter())
    registry.register(NucleiAdapter())


__all__ = [
    "ApiIntelAdapter",
    "CrawlerAdapter",
    "DnsIntelAdapter",
    "HttpxAdapter",
    "NmapAdapter",
    "NucleiAdapter",
    "TlsIntelAdapter",
    "register_builtin_adapters",
]
