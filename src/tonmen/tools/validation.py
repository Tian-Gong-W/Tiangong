from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any
from urllib.parse import urlparse

_SAFE_TARGET = re.compile(r"^[A-Za-z0-9._:\-\[\]]+$")


def reject_unknown_parameters(parameters: Mapping[str, Any], allowed: set[str]) -> None:
    unknown = set(parameters) - allowed
    if unknown:
        raise ValueError(f"unsupported parameters: {', '.join(sorted(unknown))}")


def validate_host_target(target: str | None) -> str:
    if not target:
        raise ValueError("target is required")
    if target.startswith("-") or not _SAFE_TARGET.fullmatch(target):
        raise ValueError("target must be a hostname or IP literal without shell syntax")
    return target


def validate_web_target(target: str | None) -> str:
    if not target:
        raise ValueError("target is required")
    if any(ch.isspace() for ch in target) or target.startswith("-"):
        raise ValueError("target contains invalid whitespace or option prefix")
    parsed = urlparse(target if "://" in target else f"https://{target}")
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("target must be an HTTP(S) URL or hostname")
    if any(ch in target for ch in [";", "|", "&", "`", "$", "\n", "\r"]):
        raise ValueError("target contains forbidden shell metacharacters")
    return target


def validate_ports(value: str) -> str:
    if not value:
        raise ValueError("ports cannot be empty")
    for part in value.split(","):
        if "-" in part:
            bits = part.split("-", 1)
            if len(bits) != 2 or not all(bit.isdigit() for bit in bits):
                raise ValueError("invalid port range")
            start, end = (int(bit) for bit in bits)
            if not (1 <= start <= end <= 65535):
                raise ValueError("port range must be within 1-65535")
        else:
            if not part.isdigit() or not (1 <= int(part) <= 65535):
                raise ValueError("ports must be within 1-65535")
    return value
