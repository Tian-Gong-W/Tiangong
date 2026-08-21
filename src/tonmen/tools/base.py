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
class CostEstimate:
    """Small, deterministic cost vector used by the adaptive planner."""

    wall_seconds: float = 0.0
    compute_units: float = 0.0
    network_requests: int = 0
    output_bytes: int = 0

    def __post_init__(self) -> None:
        if self.wall_seconds < 0 or self.compute_units < 0:
            raise ValueError("cost estimates cannot be negative")
        if self.network_requests < 0 or self.output_bytes < 0:
            raise ValueError("cost estimates cannot be negative")

    @property
    def effective_units(self) -> float:
        """Return a stable scalar for utility ranking, never zero."""

        return max(
            0.1,
            self.wall_seconds
            + self.compute_units
            + (self.network_requests * 0.25)
            + (self.output_bytes / (1024 * 1024)),
        )


@dataclass(frozen=True, slots=True)
class CapabilitySpec:
    """Semantic contract exposed to planners.

    ToolSpec remains as a compatibility subclass, while new planning code can
    reason about accepted inputs, produced evidence, modality and cost without
    depending on a concrete binary name.
    """

    name: str
    category: str
    description: str
    risk: RiskLevel
    capabilities: tuple[str, ...] = ()
    accepts: tuple[str, ...] = ()
    produces: tuple[str, ...] = ()
    modalities: tuple[str, ...] = ()
    estimated_cost: CostEstimate = field(default_factory=CostEstimate)
    replayable: bool = True
    isolation_profile: str = "default"
    requires_approval: bool = False
    default_parameters: tuple[tuple[str, Any], ...] = ()


@dataclass(frozen=True, slots=True)
class ToolSpec(CapabilitySpec):
    """Backward-compatible concrete-tool specialization of CapabilitySpec."""


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

    spec: CapabilitySpec

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
