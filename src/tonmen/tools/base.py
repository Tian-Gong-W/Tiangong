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
    """Coarse planner-facing cost estimate for one capability invocation."""

    wall_seconds: float = 1.0
    compute_units: float = 0.0
    network_requests: int = 0
    output_bytes: int = 0

    @property
    def effective_cost(self) -> float:
        # Keep the score stable and positive without pretending that unlike units
        # are directly comparable. More sophisticated budget managers can replace
        # this heuristic later without changing CapabilitySpec.
        return max(
            0.001,
            float(self.wall_seconds)
            + float(self.compute_units)
            + (float(self.network_requests) * 0.05)
            + (float(self.output_bytes) / 1_000_000.0),
        )


@dataclass(frozen=True, slots=True)
class CapabilitySpec:
    """Semantic contract exposed to adaptive planners.

    A CapabilitySpec describes what an adapter can consume/produce and the default
    governance characteristics of using it. It deliberately does not grant any
    execution authority; Scope, Policy and Approval remain authoritative.
    """

    name: str
    category: str
    description: str
    risk: RiskLevel
    version: str = "1"
    capabilities: tuple[str, ...] = ()
    accepts: tuple[str, ...] = ()
    produces: tuple[str, ...] = ()
    modalities: tuple[str, ...] = ()
    cost: CostEstimate = field(default_factory=CostEstimate)
    replayable: bool = True
    isolation_profile: str = "default"
    requires_approval: bool = False


@dataclass(frozen=True, slots=True)
class ToolSpec:
    name: str
    category: str
    description: str
    risk: RiskLevel
    capabilities: tuple[str, ...] = ()

    def as_capability(self) -> CapabilitySpec:
        """Expose legacy adapters through the adaptive capability interface."""
        return CapabilitySpec(
            name=self.name,
            category=self.category,
            description=self.description,
            risk=self.risk,
            capabilities=self.capabilities,
        )


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

    @property
    def capability(self) -> CapabilitySpec:
        return self.spec.as_capability()

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
