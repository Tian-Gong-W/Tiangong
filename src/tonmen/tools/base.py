from __future__ import annotations

import shutil
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Mapping, Sequence


class RiskLevel(IntEnum):
    PASSIVE = 0
    DISCOVERY = 1
    ACTIVE = 2
    VALIDATION = 3
    INTRUSIVE = 4
    DESTRUCTIVE = 5


@dataclass(frozen=True, slots=True)
class ToolSpec:
    name: str
    category: str
    description: str
    risk: RiskLevel
    capabilities: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ToolRequest:
    tool: str
    parameters: Mapping[str, Any] = field(default_factory=dict)
    target: str | None = None
    context: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ToolResult:
    tool: str
    success: bool
    summary: str
    evidence: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ToolReadiness:
    ready: bool
    code: str
    detail: str
    remediation: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


class ToolAdapter(ABC):
    """Typed capability boundary. Implementations must not accept raw shell strings."""

    spec: ToolSpec

    def readiness(self) -> ToolReadiness:
        """Describe whether the local adapter dependency can execute now."""
        path = shutil.which(self.spec.name)
        if path:
            return ToolReadiness(True, "ready", f"binary ready: {path}", metadata={"path": path})
        return ToolReadiness(
            False,
            "missing_binary",
            f"{self.spec.name} is not available in PATH",
            remediation=f"Install {self.spec.name} and make sure it is available in PATH.",
        )

    @abstractmethod
    def validate(self, request: ToolRequest) -> None:
        """Raise ValueError when a request is malformed or outside adapter semantics."""

    @abstractmethod
    def build_argv(self, request: ToolRequest) -> Sequence[str]:
        """Return an argv sequence suitable for shell=False execution."""
