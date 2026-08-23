from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from tonmen.policy.engine import Decision, PolicyEngine

from .base import ToolRequest
from .capability import CapabilityRequest, CapabilityResolution
from .registry import ToolRegistry


class CapabilityResolver:
    """Late-bind abstract evidence requests to registered governed adapters."""

    def __init__(self, registry: ToolRegistry, policy: PolicyEngine) -> None:
        self.registry = registry
        self.policy = policy

    @staticmethod
    def _host_target(target: str) -> str:
        parsed = urlparse(target if "://" in target else f"scheme://{target}")
        return parsed.hostname or target

    @classmethod
    def _target_for(cls, accepts: tuple[str, ...], target: str) -> str:
        if accepts and "url" not in accepts and "host" in accepts:
            return cls._host_target(target)
        return target

    def rank(self, request: CapabilityRequest, *, world: Any | None = None) -> tuple[CapabilityResolution, ...]:
        requested_products = set(request.required_products)
        requested_modalities = set(request.preferred_modalities)
        accepted_capabilities = set(request.accepted_capabilities)
        resolutions: list[CapabilityResolution] = []

        for adapter in self.registry:
            spec = adapter.spec
            if int(spec.risk) > request.max_risk:
                continue
            if request.replayable_required and not spec.replayable:
                continue
            cost = spec.estimated_cost.effective_units
            if request.max_cost_units is not None and cost > request.max_cost_units:
                continue

            products = set(spec.produces)
            modalities = set(spec.modalities)
            capabilities = set(spec.capabilities)
            matched_products = tuple(product for product in request.required_products if product in products)
            matched_modalities = tuple(modality for modality in request.preferred_modalities if modality in modalities)

            if request.require_product_match and requested_products and not matched_products:
                continue
            if accepted_capabilities and not accepted_capabilities.intersection(capabilities):
                continue

            target = self._target_for(spec.accepts, request.target)
            if world is not None:
                if hasattr(world, "was_attempted") and world.was_attempted(spec.name, target):
                    continue
                if hasattr(world, "is_capability_blocked") and world.is_capability_blocked(spec.name, target):
                    continue

            parameters = dict(spec.default_parameters)
            tool_request = ToolRequest(tool=spec.name, target=target, parameters=parameters)
            try:
                adapter.validate(tool_request)
            except ValueError:
                continue

            policy = self.policy.evaluate(spec, tool_request)
            if policy.decision is Decision.DENY:
                continue

            product_fraction = (
                len(matched_products) / len(requested_products)
                if requested_products
                else 0.5
            )
            modality_fraction = (
                len(matched_modalities) / len(requested_modalities)
                if requested_modalities
                else 0.0
            )
            novelty_floor = 0.25 if requested_products and not matched_products else 0.0
            relevance = 1.0 + (0.55 * product_fraction) + (0.15 * modality_fraction) + novelty_floor
            approval_penalty = 1.15 if policy.decision is Decision.REQUIRE_APPROVAL or spec.requires_approval else 1.0
            score = (max(0.01, request.expected_info_gain) * relevance) / (cost * approval_penalty)

            resolutions.append(
                CapabilityResolution(
                    request_id=request.id,
                    tool=spec.name,
                    target=target,
                    parameters=parameters,
                    score=score,
                    matched_products=matched_products,
                    matched_modalities=matched_modalities,
                    requires_approval=(policy.decision is Decision.REQUIRE_APPROVAL or spec.requires_approval),
                    risk=int(spec.risk),
                    cost_units=cost,
                )
            )

        resolutions.sort(key=lambda item: (item.score, len(item.matched_products), -item.cost_units), reverse=True)
        return tuple(resolutions)

    def resolve(self, request: CapabilityRequest, *, world: Any | None = None) -> CapabilityResolution | None:
        ranked = self.rank(request, world=world)
        return ranked[0] if ranked else None
