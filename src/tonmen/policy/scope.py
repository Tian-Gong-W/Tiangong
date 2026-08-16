from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from urllib.parse import urlparse


def _host_from_target(target: str) -> str:
    parsed = urlparse(target if "://" in target else f"scheme://{target}")
    host = parsed.hostname
    if not host:
        raise ValueError("target has no host")
    return host.rstrip(".").lower()


def _matches(host: str, rule: str) -> bool:
    rule = rule.strip().lower()
    if not rule:
        return False
    if rule.startswith("*."):
        suffix = rule[1:]
        return host.endswith(suffix) and host != suffix.lstrip(".")
    try:
        network = ipaddress.ip_network(rule, strict=False)
        return ipaddress.ip_address(host) in network
    except ValueError:
        return host == rule.rstrip(".")


@dataclass(frozen=True, slots=True)
class TargetScope:
    allowed: tuple[str, ...]
    denied: tuple[str, ...] = ()

    def is_allowed(self, target: str | None) -> bool:
        if not target:
            return False
        host = _host_from_target(target)
        if any(_matches(host, rule) for rule in self.denied):
            return False
        return any(_matches(host, rule) for rule in self.allowed)
