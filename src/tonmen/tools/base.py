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
class CapabilityPlanningSpec:
    """Declarative metadata consumed by the adaptive capability catalog.

    This metadata describes epistemic prerequisites and bounded planning cost. It does
    not grant execution authority. A planner may select a ToolSpec only after the
    normal Scope / Policy / Approval / typed-adapter path accepts the resulting step.
    """

    target_kinds: tuple[str, ...] = ("host", "web")
    seed_for: tuple[str, ...] = ()
    target_mode: str = "as_is"
    requires_profile: tuple[str, ...] = ()
    requires_capabilities: tuple[str, ...] = ()
    basis_fact_kinds: tuple[str, ...] = ()
    resolves_unknowns: tuple[str, ...] = ()
    default_parameters: Mapping[str, Any] = field(default_factory=dict)
    rationale: str = ""
    information_gain: str = ""
    information_gain_score: float = 0.5
    cost_score: float = 0.5
    include_in_baseline_envelope: bool = True

    def __post_init__(self) -> None:
        allowed_kinds = {"host", "web"}
        if not self.target_kinds or any(item not in allowed_kinds for item in self.target_kinds):
            raise ValueError("planning target_kinds must contain only host/web")
        if any(item not in allowed_kinds for item in self.seed_for):
            raise ValueError("planning seed_for must contain only host/web")
        if self.target_mode not in {"as_is", "host"}:
            raise ValueError("planning target_mode must be as_is or host")
        if not 0.0 <= float(self.information_gain_score) <= 1.0:
            raise ValueError("planning information_gain_score must be between 0 and 1")
        if not 0.0 <= float(self.cost_score) <= 1.0:
            raise ValueError("planning cost_score must be between 0 and 1")


@dataclass(frozen=True, slots=True)
class ToolSpec:
    name: str
    category: str
    description: str
    risk: RiskLevel
    capabilities: tuple[str, ...] = ()
    planning: CapabilityPlanningSpec | None = None


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
        path = shutil.which(self.spec.name)
        if path:
            return ToolReadiness(True, "ready", f"binary ready: {path}", metadata={"path": path})
        return ToolReadiness(
            False,
            "missing_binary",
            f"{self.spec.name} is not available in PATH",
            remediation=f"Install {self.spec.name} and make sure it is available in PATH.",
        )

    def adapt_parameters(self, request: ToolRequest, context: Mapping[str, Any]) -> Mapping[str, Any]:
        self.validate(request)
        return dict(request.parameters)

    @abstractmethod
    def validate(self, request: ToolRequest) -> None:
        """Raise ValueError when a request is malformed or outside adapter semantics."""

    @abstractmethod
    def build_argv(self, request: ToolRequest) -> Sequence[str]:
        """Return an argv sequence suitable for shell=False execution."""
