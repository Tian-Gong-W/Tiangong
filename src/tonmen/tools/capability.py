from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping
from uuid import uuid4


@dataclass(frozen=True, slots=True)
class CapabilityRequest:
    """Tool-independent request for evidence-producing capability.

    ``required_products`` describes desired evidence. Exploration is non-strict by
    default so a novel modality can still outrank the expected route; callers may
    set ``require_product_match=True`` for narrow validation requests.
    """

    id: str
    target: str
    required_products: tuple[str, ...] = ()
    preferred_modalities: tuple[str, ...] = ()
    accepted_capabilities: tuple[str, ...] = ()
    max_risk: int = 2
    max_cost_units: float | None = None
    replayable_required: bool = False
    require_product_match: bool = False
    hypothesis_id: str | None = None
    rationale: str = ""
    expected_info_gain: float = 0.5
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        *,
        target: str,
        required_products: tuple[str, ...] | list[str] = (),
        preferred_modalities: tuple[str, ...] | list[str] = (),
        accepted_capabilities: tuple[str, ...] | list[str] = (),
        max_risk: int = 2,
        max_cost_units: float | None = None,
        replayable_required: bool = False,
        require_product_match: bool = False,
        hypothesis_id: str | None = None,
        rationale: str = "",
        expected_info_gain: float = 0.5,
        metadata: Mapping[str, Any] | None = None,
    ) -> "CapabilityRequest":
        if max_risk < 0:
            raise ValueError("max_risk cannot be negative")
        if max_cost_units is not None and max_cost_units <= 0:
            raise ValueError("max_cost_units must be positive when provided")
        return cls(
            id=uuid4().hex,
            target=str(target),
            required_products=tuple(dict.fromkeys(str(item) for item in required_products if str(item))),
            preferred_modalities=tuple(dict.fromkeys(str(item) for item in preferred_modalities if str(item))),
            accepted_capabilities=tuple(dict.fromkeys(str(item) for item in accepted_capabilities if str(item))),
            max_risk=int(max_risk),
            max_cost_units=float(max_cost_units) if max_cost_units is not None else None,
            replayable_required=bool(replayable_required),
            require_product_match=bool(require_product_match),
            hypothesis_id=hypothesis_id,
            rationale=str(rationale),
            expected_info_gain=max(0.0, min(1.0, float(expected_info_gain))),
            metadata=dict(metadata or {}),
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "target": self.target,
            "required_products": list(self.required_products),
            "preferred_modalities": list(self.preferred_modalities),
            "accepted_capabilities": list(self.accepted_capabilities),
            "max_risk": self.max_risk,
            "max_cost_units": self.max_cost_units,
            "replayable_required": self.replayable_required,
            "require_product_match": self.require_product_match,
            "hypothesis_id": self.hypothesis_id,
            "rationale": self.rationale,
            "expected_info_gain": self.expected_info_gain,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class CapabilityResolution:
    request_id: str
    tool: str
    target: str
    parameters: Mapping[str, Any]
    score: float
    matched_products: tuple[str, ...]
    matched_modalities: tuple[str, ...]
    requires_approval: bool
    risk: int
    cost_units: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "tool": self.tool,
            "target": self.target,
            "parameters": dict(self.parameters),
            "score": self.score,
            "matched_products": list(self.matched_products),
            "matched_modalities": list(self.matched_modalities),
            "requires_approval": self.requires_approval,
            "risk": self.risk,
            "cost_units": self.cost_units,
        }
