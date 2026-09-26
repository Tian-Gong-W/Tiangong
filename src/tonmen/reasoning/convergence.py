from __future__ import annotations

from dataclasses import dataclass

from tonmen.missions import MissionRun


@dataclass(frozen=True, slots=True)
class ConvergenceReport:
    converged: bool
    reason: str
    open_hypotheses: int
    recent_fact_gain: int
    recent_proposal_gain: int
    max_expected_info_gain: float


class ConvergenceDetector:
    """Decide when further autonomous work has near-zero information value.

    Self-reliance includes knowing when to stop — not only when to re-plan.
    """

    def __init__(
        self,
        *,
        min_idle_rounds: int = 2,
        min_info_gain_threshold: float = 0.35,
    ) -> None:
        self.min_idle_rounds = max(1, min_idle_rounds)
        self.min_info_gain_threshold = max(0.0, min(1.0, min_info_gain_threshold))
        self._idle_rounds = 0
        self._last_fact_count = 0
        self._last_proposal_count = 0

    def observe(self, run: MissionRun, *, max_expected_info_gain: float = 0.0) -> ConvergenceReport:
        facts = sum(1 for n in run.graph.nodes.values() if n.kind.startswith("intelligence."))
        proposals = sum(1 for n in run.graph.nodes.values() if n.kind == "action_proposal")
        open_hypos = sum(
            1
            for n in run.graph.nodes.values()
            if n.kind == "hypothesis" and str(n.metadata.get("status", "open")).lower() == "open"
        )

        fact_gain = max(0, facts - self._last_fact_count)
        proposal_gain = max(0, proposals - self._last_proposal_count)
        self._last_fact_count = facts
        self._last_proposal_count = proposals

        productive = fact_gain > 0 or (
            proposal_gain > 0 and max_expected_info_gain >= self.min_info_gain_threshold
        )
        if productive:
            self._idle_rounds = 0
        else:
            self._idle_rounds += 1

        converged = False
        reason = "still exploring"
        if self._idle_rounds >= self.min_idle_rounds and open_hypos == 0:
            converged = True
            reason = "no open hypotheses and no recent information gain"
        elif self._idle_rounds >= self.min_idle_rounds and max_expected_info_gain < self.min_info_gain_threshold:
            converged = True
            reason = (
                f"{self._idle_rounds} idle rounds with max expected info gain "
                f"{max_expected_info_gain:.2f} below threshold {self.min_info_gain_threshold:.2f}"
            )

        return ConvergenceReport(
            converged=converged,
            reason=reason,
            open_hypotheses=open_hypos,
            recent_fact_gain=fact_gain,
            recent_proposal_gain=proposal_gain,
            max_expected_info_gain=max_expected_info_gain,
        )
