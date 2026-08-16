from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass
from urllib.parse import urlparse

_HOST_RULE = re.compile(
    r"^(?:\*\.)?(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)*"
    r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$",
    re.IGNORECASE,
)


def _host_from_target(target: str) -> str:
    parsed = urlparse(target if "://" in target else f"scheme://{target}")
    host = parsed.hostname
    if not host:
        raise ValueError("target has no host")
    return host.rstrip(".").lower()


def validate_scope_rule(rule: str) -> str:
    value = str(rule).strip().lower()
    if not value or any(ch.isspace() for ch in value):
        raise ValueError("scope rule cannot be empty or contain whitespace")
    if any(ch in value for ch in (";", "|", "&", "`", "$", "\n", "\r")):
        raise ValueError("scope rule contains forbidden shell metacharacters")

    try:
        return str(ipaddress.ip_network(value, strict=False))
    except ValueError:
        pass

    hostname = value[2:] if value.startswith("*.") else value
    if not hostname or not _HOST_RULE.fullmatch(value):
        raise ValueError("scope rule must be a hostname, IP/CIDR, or leading wildcard hostname")
    return value


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
