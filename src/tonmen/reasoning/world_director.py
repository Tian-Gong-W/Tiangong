from __future__ import annotations

from dataclasses import dataclass, replace

from tonmen.missions import MissionPlan, MissionRun
from tonmen.tools import CapabilityRequest, CapabilityResolution, RiskLevel
from tonmen.tools.resolver import CapabilityResolver

from .director import MissionDirector as _LegacyCapabilityDirector
from .director import _CapabilityCandidate
from .model import Hypothesis, HypothesisStatus, ReasoningDecision
from .world import WorldModel


@dataclass(frozen=True, slots=True)
class _RequestedCandidate(_CapabilityCandidate):
    request: CapabilityRequest
    resolution: CapabilityResolution


class MissionDirector(_LegacyCapabilityDirector):
    """WorldModel Director that asks for evidence before selecting an adapter.

    The Director forms a tool-independent CapabilityRequest from current evidence
    needs. CapabilityResolver performs late binding against the current Registry,
    Policy and learned capability envelope. Concrete tool identity is therefore a
    resolution result, not the research question itself.
    """

    @staticmethod
    def _world(run: MissionRun, registry=None) -> WorldModel:
        return WorldModel.from_run(run, registry=registry)

    @staticmethod
    def _initial_hypothesis(run: MissionRun) -> Hypothesis | None:
        if any(node.kind == "hypothesis" for node in run.graph.nodes.values()):
            return None
        return Hypothesis.create(
            statement=(
                f"Authorized target {run.target} may expose observable network or web behavior "
                "that can be characterized by evidence."
            ),
            confidence=0.5,
            status=HypothesisStatus.OPEN,
            metadata={
                "kind": "bootstrap",
                "source": "mission_director",
                "evidence_need": "characterize the observable target surface",
                "required_products": ["service_observation", "http_observation"],
                "preferred_modalities": ["network", "http"],
            },
        )

    @classmethod
    def _attempted_actions(cls, plan: MissionPlan, run: MissionRun) -> set[tuple[str, str]]:
        return set(cls._world(run).attempted_actions)

    def _observed_modalities(self, plan: MissionPlan, run: MissionRun) -> set[str]:
        registry = self.runtime.registry if self.runtime is not None else None
        return set(self._world(run, registry).observed_modalities)

    @staticmethod
    def _observed_products(run: MissionRun) -> set[str]:
        return set(WorldModel.from_run(run).observed_products)

    def _capability_request(
        self,
        plan: MissionPlan,
        run: MissionRun,
        hypotheses: tuple[Hypothesis, ...],
    ) -> CapabilityRequest:
        registry = self.runtime.registry if self.runtime is not None else None
        model = self._world(run, registry)
        open_hypotheses = [item for item in hypotheses if item.status is HypothesisStatus.OPEN]
        supported = [item for item in hypotheses if item.status is HypothesisStatus.SUPPORTED]

        products: list[str] = list(model.missing_products())
        modalities: list[str] = [
            modality
            for need in model.evidence_needs
            for modality in need.preferred_modalities
            if modality
        ]
        descriptions = [need.description for need in model.evidence_needs if need.description]

        for hypothesis in open_hypotheses:
            metadata = dict(hypothesis.metadata)
            for product in metadata.get("required_products", ()):
                text = str(product)
                if text and text not in products:
                    products.append(text)
            for modality in metadata.get("preferred_modalities", ()):
                text = str(modality)
                if text and text not in modalities:
                    modalities.append(text)
            description = str(metadata.get("evidence_need") or "")
            if description and description not in descriptions:
                descriptions.append(description)

        if supported and not open_hypotheses:
            products = ["validation_observation", "finding"]
            if not modalities:
                modalities = list(model.observed_modalities) or ["http"]
            max_risk = int(RiskLevel.VALIDATION)
            strict = True
            hypothesis_id = supported[0].id
            rationale = "seek bounded validation evidence for the supported hypothesis"
        else:
            max_risk = int(RiskLevel.ACTIVE)
            strict = False
            hypothesis_id = open_hypotheses[0].id if open_hypotheses else None
            rationale = "; ".join(descriptions) or "reduce current mission uncertainty with new evidence"

        return CapabilityRequest.create(
            target=plan.target,
            required_products=products,
            preferred_modalities=modalities,
            max_risk=max_risk,
            require_product_match=strict,
            hypothesis_id=hypothesis_id,
            rationale=rationale,
            expected_info_gain=1.0,
            metadata={
                "authority": "mission_director",
                "open_hypothesis_ids": [item.id for item in open_hypotheses],
                "supported_hypothesis_ids": [item.id for item in supported],
            },
        )

    def _rank_capabilities(
        self,
        plan: MissionPlan,
        run: MissionRun,
        hypotheses: tuple[Hypothesis, ...],
    ) -> list[_CapabilityCandidate]:
        if self.runtime is None:
            return []

        world = self._world(run, self.runtime.registry)
        request = self._capability_request(plan, run, hypotheses)
        resolver = CapabilityResolver(self.runtime.registry, self.runtime.policy)
        resolutions = resolver.rank(request, world=world)
        observed_products = set(world.observed_products)
        observed_modalities = set(world.observed_modalities)
        candidates: list[_CapabilityCandidate] = []

        for resolution in resolutions:
            spec = self.runtime.registry.get(resolution.tool).spec
            gain, missing = self._information_gain(
                spec,
                observed_modalities=observed_modalities,
                observed_products=observed_products,
            )
            if gain <= 0:
                continue
            candidates.append(
                _RequestedCandidate(
                    spec=spec,
                    target=resolution.target,
                    parameters=dict(resolution.parameters),
                    missing_products=missing,
                    information_gain=gain,
                    utility=resolution.score * max(0.1, gain),
                    requires_approval=resolution.requires_approval,
                    request=request,
                    resolution=resolution,
                )
            )

        candidates.sort(key=lambda item: (item.utility, item.information_gain), reverse=True)
        return candidates

    def _candidate_decision(
        self,
        plan: MissionPlan,
        run: MissionRun,
        candidate: _CapabilityCandidate,
        hypotheses: tuple[Hypothesis, ...],
    ) -> ReasoningDecision:
        decision = super()._candidate_decision(plan, run, candidate, hypotheses)
        if not isinstance(candidate, _RequestedCandidate):
            return decision

        request = candidate.request
        resolution = candidate.resolution
        summary = f"{decision.summary} CapabilityRequest {request.id[:8]} resolved to {resolution.tool}."
        if not decision.new_proposals:
            return replace(decision, summary=summary)

        proposal = decision.new_proposals[0]
        enriched = replace(
            proposal,
            metadata={
                **dict(proposal.metadata),
                "capability_request": request.as_dict(),
                "capability_resolution": resolution.as_dict(),
                "adapter_late_bound": True,
            },
        )
        return replace(decision, summary=summary, new_proposals=(enriched,))
