from __future__ import annotations

from typing import Any

from .engine import AssessmentCouncil as BaseAssessmentCouncil


class AssessmentCouncil(BaseAssessmentCouncil):
    """Assessment Council that restores Provider Hub usage from Mission provenance.

    MissionLoop resume creates a fresh Council instance. Before each new round we
    rebuild provider token/failure counters from persisted council.subagent nodes so
    TONMEN-local per-mission budgets cannot be reset simply by resuming a mission.
    """

    def record_round(self, plan: Any, run: Any, **kwargs: Any) -> str | None:
        prime = getattr(self.provider_hub, "prime_usage_from_run", None)
        if callable(prime):
            prime(run)
        return super().record_round(plan, run, **kwargs)
