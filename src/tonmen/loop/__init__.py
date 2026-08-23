from tonmen.missions import classify_proposal_outcome, record_action_outcome
from tonmen.reasoning import MissionDirector

from .director_engine import MissionLoop as _DirectorMissionLoop
from .model import LoopStopReason, MissionLoopPolicy, MissionLoopResult


class MissionLoop(_DirectorMissionLoop):
    """Public Director-first loop with WorldModel and structured Action outcomes."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.director = MissionDirector(self.runtime, reasoner=self.reasoner)
        self.reasoner = self.director.reasoner

    def _emit(self, event_type, run, **data) -> None:
        # `target` is reserved by the base event envelope for Mission identity.
        # Dynamic proposal events historically also used `target`, which only
        # surfaced once P4 caused more late-bound proposals on Console runtimes.
        # Preserve both meanings without duplicate keyword collisions.
        if "target" in data:
            data = {"action_target": data["target"], **{key: value for key, value in data.items() if key != "target"}}
        super()._emit(event_type, run, **data)

    def _schedule_one_proposal(self, run, decision, *, approval_tokens, plan=None) -> int:
        proposal = decision.new_proposals[0]
        scheduled = super()._schedule_one_proposal(
            run,
            decision,
            approval_tokens=approval_tokens,
            plan=plan,
        )
        accepted = scheduled > 0 or run.state.value == "waiting_approval"
        outcome = record_action_outcome(
            run,
            classify_proposal_outcome(run, proposal, accepted),
        )
        self._emit(
            "action.outcome",
            run,
            outcome_id=outcome.id,
            action_id=outcome.action_id,
            proposal_id=outcome.proposal_id,
            kind=outcome.kind.value,
            evidence_bearing=outcome.evidence_bearing,
            may_revise_belief=outcome.may_revise_belief,
        )
        return scheduled


__all__ = ["LoopStopReason", "MissionLoop", "MissionLoopPolicy", "MissionLoopResult"]
