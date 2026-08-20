from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from typing import Any, Callable
from urllib.parse import urlparse

from tonmen.policy import TargetScope


@dataclass(frozen=True, slots=True)
class ResolvedAsset:
    address: str
    family: str
    authorized: bool
    scope_status: str
    source: str = "dns"

    def as_dict(self) -> dict[str, object]:
        return {
            "address": self.address,
            "family": self.family,
            "authorized": self.authorized,
            "scope_status": self.scope_status,
            "source": self.source,
        }


def _target_host(target: str) -> str:
    parsed = urlparse(target if "://" in target else f"scheme://{target}")
    if not parsed.hostname:
        raise ValueError("target has no hostname")
    return parsed.hostname.rstrip(".").lower()


def _family_name(address: str) -> str:
    return "ipv6" if ipaddress.ip_address(address).version == 6 else "ipv4"


def _default_resolver(host: str) -> list[str]:
    values: list[str] = []
    for item in socket.getaddrinfo(host, None, type=socket.SOCK_STREAM):
        sockaddr = item[4]
        if not sockaddr:
            continue
        raw = str(sockaddr[0]).split("%", 1)[0]
        try:
            normalized = str(ipaddress.ip_address(raw))
        except ValueError:
            continue
        if normalized not in values:
            values.append(normalized)
    return values


def build_resolved_asset_set(
    target: str,
    scope: TargetScope,
    *,
    resolver: Callable[[str], list[str]] | None = None,
) -> dict[str, Any]:
    """Resolve one governed target into a passive asset set.

    Resolution creates observations only. An address becomes eligible for direct
    coverage steps only when that concrete IP is already independently allowed by
    TargetScope. Authorizing the hostname does not implicitly authorize each DNS
    answer as a direct execution target.
    """

    host = _target_host(target)
    try:
        literal = str(ipaddress.ip_address(host))
    except ValueError:
        literal = None

    resolution_error: str | None = None
    if literal is not None:
        addresses = [literal]
    else:
        try:
            addresses = (resolver or _default_resolver)(host)
        except OSError as exc:
            addresses = []
            resolution_error = str(exc)[:240]

    assets: list[ResolvedAsset] = []
    for raw in addresses:
        try:
            address = str(ipaddress.ip_address(str(raw).split("%", 1)[0]))
        except ValueError:
            continue
        if any(item.address == address for item in assets):
            continue
        authorized = scope.is_allowed(address)
        assets.append(
            ResolvedAsset(
                address=address,
                family=_family_name(address),
                authorized=authorized,
                scope_status="authorized" if authorized else "needs_scope",
            )
        )

    assets.sort(key=lambda item: (item.family == "ipv6", ipaddress.ip_address(item.address)))
    authorized = [item.address for item in assets if item.authorized]
    needs_scope = [item.address for item in assets if not item.authorized]
    return {
        "target": target,
        "host": host,
        "resolution_status": "error" if resolution_error else ("resolved" if assets else "no_addresses"),
        "resolution_error": resolution_error,
        "assets": [item.as_dict() for item in assets],
        "authorized_addresses": authorized,
        "needs_scope": needs_scope,
        "scope_snapshot": {
            "allowed": list(scope.allowed),
            "denied": list(scope.denied),
        },
        "semantics": {
            "dns_resolution_expands_scope": False,
            "direct_ip_execution_requires_ip_scope": True,
            "web_target_preserves_hostname": True,
        },
    }
