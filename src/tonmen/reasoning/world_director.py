from __future__ import annotations

from tonmen.missions import MissionPlan, MissionRun
from tonmen.policy import Decision
from tonmen.tools import RiskLevel, ToolRequest

from .director import MissionDirector as _LegacyCapabilityDirector
from .director import _CapabilityCandidate
from .model import Hypothesis, HypothesisStatus
from .world import WorldModel


class MissionDirector(_LegacyCapabilityDirector):
    """Capability Director backed by one canonical WorldModel projection.

    The P1 Director remains the compatibility implementation underneath. This
    layer removes its scattered graph/action scans from the selection path and
    makes environment failures part of the current world state.
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
        model = cls._world(run)
        return set(model.attempted_actions)

    def _observed_modalities(self, plan: MissionPlan, run: MissionRun) -> set[str]:
        registry = self.runtime.registry if self.runtime is not None else None
        return set(self._world(run, registry).observed_modalities)

    @staticmethod
    def _observed_products(run: MissionRun) -> set[str]:
        return set(WorldModel.from_run(run).observed_products)

    def _rank_capabilities(
        self,
        plan: MissionPlan,
        run: MissionRun,
        hypotheses: tuple[Hypothesis, ...],
    ) -> list[_CapabilityCandidate]:
        if self.runtime is None:
            return []

        model = self._world(run, self.runtime.registry)
        supported = any(item.status is HypothesisStatus.SUPPORTED for item in hypotheses)
        requested_products = set(model.missing_products())
        requested_modalities = {
            modality
            for need in model.evidence_needs
            for modality in need.preferred_modalities
        }
        observed_products = set(model.observed_products)
        observed_modalities = set(model.observed_modalities)
        candidates: list[_CapabilityCandidate] = []

        for adapter in self.runtime.registry:
            spec = adapter.spec
            target = self._target_for(spec, plan.target)

            if spec.risk >= RiskLevel.DESTRUCTIVE:
                continue
            if spec.risk >= RiskLevel.VALIDATION and not supported:
                continue
            if model.was_attempted(spec.name, target):
                continue
            if model.is_capability_blocked(spec.name, target):
                continue

            parameters = dict(spec.default_parameters)
            request = ToolRequest(tool=spec.name, target=target, parameters=parameters)
            try:
                adapter.validate(request)
            except ValueError:
                continue
            policy = self.runtime.policy.evaluate(spec, request)
            if policy.decision is Decision.DENY:
                continue

            gain, missing = self._information_gain(
                spec,
                observed_modalities=observed_modalities,
                observed_products=observed_products,
            )
            if gain <= 0:
                continue

            # EvidenceNeed is a relevance signal, not another fixed ladder. A new
            # capability may still win without matching the bootstrap vocabulary,
            # but capabilities that directly answer an explicit need rank higher.
            product_match = len(requested_products.intersection(spec.produces))
            modality_match = len(requested_modalities.intersection(spec.modalities))
            relevance = 1.0 + (0.35 * product_match) + (0.10 * modality_match)
            cost = spec.estimated_cost.effective_units
            approval_penalty = 1.15 if policy.decision is Decision.REQUIRE_APPROVAL or spec.requires_approval else 1.0
            candidates.append(
                _CapabilityCandidate(
                    spec=spec,
                    target=target,
                    parameters=parameters,
                    missing_products=missing,
                    information_gain=gain,
                    utility=(gain * relevance) / (cost * approval_penalty),
                    requires_approval=(policy.decision is Decision.REQUIRE_APPROVAL or spec.requires_approval),
                )
            )

        candidates.sort(key=lambda item: (item.utility, item.information_gain), reverse=True)
        return candidates
