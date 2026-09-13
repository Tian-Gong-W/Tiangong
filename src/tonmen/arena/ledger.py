from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .models import LeadHandoverEvent, SubagentLootEvent


@dataclass
class StrategistProfile:
    id: str
    name: str
    model: str
    subagents_count: int = 3
    total_score: float = 0.0
    recent_scores: List[float] = field(default_factory=list)
    accuracy_history: List[float] = field(default_factory=list)
    success_rate_history: List[float] = field(default_factory=list)
    risk_reward_history: List[float] = field(default_factory=list)
    wins: int = 0
    rounds_participated: int = 0
    tactical_experience: Dict[str, Any] = field(default_factory=dict)
    is_leader: bool = False
    consecutive_leads: int = 0

    @property
    def avg_accuracy(self) -> float:
        if not self.accuracy_history:
            return 90.0
        return sum(self.accuracy_history[-10:]) / len(self.accuracy_history[-10:])

    @property
    def avg_success_rate(self) -> float:
        if not self.success_rate_history:
            return 85.0
        return sum(self.success_rate_history[-10:]) / len(self.success_rate_history[-10:])

    @property
    def avg_risk_reward(self) -> float:
        if not self.risk_reward_history:
            return 88.0
        return sum(self.risk_reward_history[-10:]) / len(self.risk_reward_history[-10:])

    @property
    def recent_score(self) -> float:
        if not self.recent_scores:
            return 0.0
        # Exponential moving average of recent 5 rounds
        weights = [0.1, 0.15, 0.2, 0.25, 0.3][-len(self.recent_scores):]
        w_sum = sum(weights)
        return sum(s * w for s, w in zip(self.recent_scores[-5:], weights)) / w_sum


class ArenaLedger:
    """Manages agent points, compute quotas, subagent allocations, and Matthew effect looting."""

    def __init__(
        self,
        lead_margin_threshold: float = 0.30,  # 30% lead
        lead_consecutive_rounds: int = 2,     # consecutive 2 rounds
        epoch_shuffle_interval: int = 50,     # every 50 rounds
    ) -> None:
        self.strategists: Dict[str, StrategistProfile] = {}
        self.current_round: int = 0
        self.current_leader_id: Optional[str] = None
        self.lead_margin_threshold = lead_margin_threshold
        self.lead_consecutive_rounds = lead_consecutive_rounds
        self.epoch_shuffle_interval = epoch_shuffle_interval
        self.handover_history: List[LeadHandoverEvent] = []
        self.loot_history: List[SubagentLootEvent] = []

    def register_strategist(self, strategist_id: str, name: str, model: str, initial_subagents: int = 3) -> None:
        self.strategists[strategist_id] = StrategistProfile(
            id=strategist_id,
            name=name,
            model=model,
            subagents_count=initial_subagents,
        )
        if self.current_leader_id is None:
            self.current_leader_id = strategist_id
            self.strategists[strategist_id].is_leader = True

    def record_round_scores(
        self,
        round_number: int,
        round_scores: Dict[str, Dict[str, float]],
    ) -> Tuple[Optional[LeadHandoverEvent], Optional[SubagentLootEvent]]:
        """Updates round scores, checks command shift, and performs subagent looting."""
        self.current_round = round_number

        for s_id, metrics in round_scores.items():
            if s_id not in self.strategists:
                continue
            profile = self.strategists[s_id]
            profile.rounds_participated += 1
            score = metrics.get("composite_score", 0.0)
            profile.total_score += score
            profile.recent_scores.append(score)
            profile.accuracy_history.append(metrics.get("accuracy", 90.0))
            profile.success_rate_history.append(metrics.get("success_rate", 85.0))
            profile.risk_reward_history.append(metrics.get("risk_reward", 88.0))

        # Check winner of this round
        sorted_by_recent = sorted(
            self.strategists.values(),
            key=lambda p: p.recent_score,
            reverse=True,
        )
        if not sorted_by_recent:
            return None, None

        best_profile = sorted_by_recent[0]
        runner_up_score = sorted_by_recent[1].recent_score if len(sorted_by_recent) > 1 else 0.0
        best_profile.wins += 1

        # Check Command Shift Handover
        handover_event = self._evaluate_command_shift(best_profile, runner_up_score)

        # Check Subagent Looting: The bottom agent loses 1 subagent to the top winner
        loot_event = self._evaluate_subagent_looting(sorted_by_recent)

        return handover_event, loot_event

    def _evaluate_command_shift(
        self,
        candidate: StrategistProfile,
        runner_up_score: float,
    ) -> Optional[LeadHandoverEvent]:
        current_leader = self.strategists.get(self.current_leader_id) if self.current_leader_id else None
        current_leader_score = current_leader.recent_score if current_leader else runner_up_score

        if candidate.id == self.current_leader_id:
            denom = max(1.0, runner_up_score)
            margin = (candidate.recent_score - runner_up_score) / denom
        else:
            denom = max(1.0, current_leader_score)
            margin = (candidate.recent_score - current_leader_score) / denom

        # Is candidate leading significantly?
        if margin >= self.lead_margin_threshold:
            candidate.consecutive_leads += 1
        else:
            candidate.consecutive_leads = 0

        # Epoch shuffle trigger
        is_epoch_shuffle = (self.current_round % self.epoch_shuffle_interval == 0) and self.current_round > 0

        should_shift = False
        reason = ""

        if is_epoch_shuffle:
            should_shift = True
            reason = f"Epoch {self.current_round} periodic strategic reshuffle"
        elif candidate.consecutive_leads >= self.lead_consecutive_rounds and candidate.id != self.current_leader_id:
            should_shift = True
            reason = f"Led by >= {self.lead_margin_threshold*100:.0f}% for {self.lead_consecutive_rounds} consecutive rounds (margin: {margin*100:.1f}%)"

        if should_shift:
            old_leader = self.current_leader_id or "none"
            if old_leader in self.strategists:
                self.strategists[old_leader].is_leader = False
            candidate.is_leader = True
            self.current_leader_id = candidate.id
            candidate.consecutive_leads = 0

            event = LeadHandoverEvent(
                event_id=f"handover-r{self.current_round}-{candidate.id}",
                round_number=self.current_round,
                from_leader=old_leader,
                to_leader=candidate.id,
                margin=margin,
                reason=reason,
            )
            self.handover_history.append(event)
            return event

        return None

    def _evaluate_subagent_looting(
        self,
        sorted_profiles: List[StrategistProfile],
    ) -> Optional[SubagentLootEvent]:
        if len(sorted_profiles) < 2:
            return None

        winner = sorted_profiles[0]
        loser = sorted_profiles[-1]

        # Loser must have at least 2 subagents (cannot drop below 1 to avoid elimination deadlock)
        if loser.subagents_count > 1 and winner.id != loser.id:
            loser.subagents_count -= 1
            winner.subagents_count += 1

            # Sanitize experience transfer (clean conversation context, transfer general heuristics)
            sanitized_exp = {
                "proven_tactics": loser.tactical_experience.get("proven_tactics", [])[:3],
                "avoid_signatures": loser.tactical_experience.get("avoid_signatures", [])[:3],
            }
            winner.tactical_experience.setdefault("proven_tactics", []).extend(sanitized_exp["proven_tactics"])

            event = SubagentLootEvent(
                event_id=f"loot-r{self.current_round}-{winner.id}-{loser.id}",
                round_number=self.current_round,
                winner_id=winner.id,
                loser_id=loser.id,
                transferred_count=1,
                sanitized_experience=sanitized_exp,
            )
            self.loot_history.append(event)
            return event

        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "current_round": self.current_round,
            "current_leader": self.current_leader_id,
            "strategists": [
                {
                    "id": p.id,
                    "name": p.name,
                    "model": p.model,
                    "subagents_count": p.subagents_count,
                    "total_score": round(p.total_score, 1),
                    "recent_score": round(p.recent_score, 1),
                    "accuracy": round(p.avg_accuracy, 1),
                    "success_rate": round(p.avg_success_rate, 1),
                    "risk_reward": round(p.avg_risk_reward, 1),
                    "wins": p.wins,
                    "is_leader": p.is_leader,
                }
                for p in self.strategists.values()
            ],
            "recent_handovers": [
                {
                    "round": h.round_number,
                    "from": h.from_leader,
                    "to": h.to_leader,
                    "reason": h.reason,
                }
                for h in self.handover_history[-5:]
            ],
            "recent_loots": [
                {
                    "round": l.round_number,
                    "winner": l.winner_id,
                    "loser": l.loser_id,
                }
                for l in self.loot_history[-5:]
            ],
        }

    def can_afford(self, strategist_id: str, cost: float) -> bool:
        if strategist_id not in self.strategists:
            return False
        return self.strategists[strategist_id].total_score >= cost

    def spend_points(self, strategist_id: str, cost: float) -> bool:
        if not self.can_afford(strategist_id, cost):
            return False
        self.strategists[strategist_id].total_score -= cost
        return True

    def reward_points(self, strategist_id: str, reward: float) -> float:
        if strategist_id in self.strategists:
            self.strategists[strategist_id].total_score += reward
            self.strategists[strategist_id].recent_scores.append(reward)
            return self.strategists[strategist_id].total_score
        return 0.0

    def force_lead_capture(self, strategist_id: str, reason: str) -> Optional[LeadHandoverEvent]:
        if strategist_id not in self.strategists or strategist_id == self.current_leader_id:
            return None
        old_leader = self.current_leader_id or "none"
        if old_leader in self.strategists:
            self.strategists[old_leader].is_leader = False
        self.strategists[strategist_id].is_leader = True
        self.current_leader_id = strategist_id
        event = LeadHandoverEvent(
            event_id=f"handover-combat-r{self.current_round}-{strategist_id}",
            round_number=self.current_round,
            from_leader=old_leader,
            to_leader=strategist_id,
            margin=1.0,
            reason=reason,
        )
        self.handover_history.append(event)
        return event
