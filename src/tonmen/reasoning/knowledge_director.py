from __future__ import annotations

from dataclasses import replace

from tonmen.knowledge import KnowledgeBroker
from tonmen.missions import MissionPlan, MissionRun
from tonmen.tools import CapabilityRequest

from .model import Hypothesis
from .world_director import MissionDirector as _WorldMissionDirector


class MissionDirector(_WorldMissionDirector):
    """Freshness-aware Director.

    The knowledge plane may change which evidence is worth collecting, but it does
    not create target facts, grant authority, select destructive actions, or bypass
    the existing CapabilityResolver / Scope / Policy / Approval path.
    """

    def _knowledge_context(self, plan: MissionPlan, run: MissionRun):
        if self.runtime is None:
            return None
        broker = KnowledgeBroker(self.runtime.config.workspace)
        return broker.context_for(run, metadata=plan.metadata)

    def _capability_request(
        self,
        plan: MissionPlan,
        run: MissionRun,
        hypotheses: tuple[Hypothesis, ...],
    ) -> CapabilityRequest:
        base = super()._capability_request(plan, run, hypotheses)
        context = self._knowledge_context(plan, run)
        if context is None or not context.active:
            return base

        products = list(base.required_products)
        for product in context.required_products:
            if product not in products:
                products.append(product)

        modalities = list(base.preferred_modalities)
        for modality in context.preferred_modalities:
            if modality not in modalities:
                modalities.append(modality)

        rationale = base.rationale
        if context.rationale:
            rationale = f"{rationale}; {context.rationale}" if rationale else context.rationale

        metadata = {
            **dict(base.metadata),
            "knowledge_context": context.as_dict(),
            "knowledge_freshness_policy": "stale_records_excluded",
            "knowledge_is_evidence": False,
        }
        return replace(
            base,
            required_products=tuple(products),
            preferred_modalities=tuple(modalities),
            rationale=rationale,
            metadata=metadata,
        )
