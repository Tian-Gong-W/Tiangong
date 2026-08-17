from __future__ import annotations

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


class ToolAdapter(ABC):
    """Typed capability boundary. Implementations must not accept raw shell strings."""

    spec: ToolSpec

    @abstractmethod
    def validate(self, request: ToolRequest) -> None:
        """Raise ValueError when a request is malformed or outside adapter semantics."""

    @abstractmethod
    def build_argv(self, request: ToolRequest) -> Sequence[str]:
        """Return an argv sequence suitable for shell=False execution."""
