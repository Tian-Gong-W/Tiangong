from __future__ import annotations

from dataclasses import replace
from typing import Any

from tonmen.ai import LeadAIOrchestrator, ProviderHub

from .engine import AssessmentCouncil as BaseAssessmentCouncil


class AssessmentCouncil(BaseAssessmentCouncil):
    """Failure-contained, opt-in Council wrapper.

    Council review is no longer a mandatory mission cadence. ``0/0`` disables it;
    non-zero values are hard ceilings only. The core runtime can therefore operate
    with one Lead and no standing review committee unless a caller explicitly opts in.
    """

    def __init__(
        self,
        *,
        target_rounds: int = 0,
        agents_per_round: int = 0,
        lead_ai: LeadAIOrchestrator | None = None,
        provider_hub: ProviderHub | None = None,
    ) -> None:
        rounds = int(target_rounds)
        agents = int(agents_per_round)
        if not 0 <= rounds <= 10:
            raise ValueError("assessment_rounds must be between 0 and 10")
        if not 0 <= agents <= 5:
            raise ValueError("subagents_per_round must be between 0 and 5")
        if (rounds == 0) != (agents == 0):
            raise ValueError("assessment_rounds and subagents_per_round must both be zero or both be enabled")

        # Initialize the same runtime dependencies as BaseAssessmentCouncil without
        # inheriting its legacy 7-10 / 3-5 prescribed ranges.
        self.target_rounds = rounds
        self.agents_per_round = agents
        self.lead_ai = lead_ai or LeadAIOrchestrator()
        self.provider_hub = provider_hub or ProviderHub()

    def _review_payload(self, role: str, plan: Any, run: Any, **kwargs: Any) -> dict[str, object]:
        # BaseAssessmentCouncil still renders frozen plan/execution pairs with a
        # strict zip. Dynamic actions live after those compatibility slots and must
        # not make an explicitly enabled Council crash during review.
        if len(run.steps) > len(plan.steps):
            run = replace(run, steps=list(run.steps[: len(plan.steps)]))
        return super()._review_payload(role, plan, run, **kwargs)

    def record_round(self, plan: Any, run: Any, **kwargs: Any) -> str | None:
        if self.target_rounds == 0 or self.agents_per_round == 0:
            return None
        if self._existing_rounds(run) >= self.target_rounds:
            return None
        return super().record_round(plan, run, **kwargs)
