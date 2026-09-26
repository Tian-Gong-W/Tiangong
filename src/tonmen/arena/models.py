from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
import time


class NodeType(str, Enum):
    OR_NODE = "OR"      # Any fulfilled parent unlocks this node (e.g. alternative entry points)
    AND_NODE = "AND"    # All parents required (e.g. exploit requires specific version + exposed port + bypass)
    STATE_NODE = "STATE"# Asset / Credential / Permission status


class LootCategory(str, Enum):
    INFO = "info"           # Fingerprint, version, rules (Low score: 2-5)
    BYPASS = "bypass"       # WAF bypass, auth bypass (Medium score: 15-30)
    ACCESS = "access"       # Low-priv account, foothold (High score: 20-35)
    ADMIN = "admin"         # High-priv credential, escalation (Critical: 35-50)
    OBJECTIVE = "objective" # Target reached / Crown jewel (Max: 100)


@dataclass
class LootItem:
    id: str
    title: str
    category: LootCategory
    confidence: float = 1.0          # 0.0 - 1.0 (verified in target)
    irreplaceability: float = 1.0    # 0.0 - 1.0 (is this the bottleneck?)
    verified: bool = True
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)
    discovered_by: Optional[str] = None


@dataclass
class TacticalProposal:
    proposal_id: str
    strategist_id: str
    hypothesis: str
    target_id: str
    preconditions: List[str] = field(default_factory=list)
    proposed_actions: List[Dict[str, Any]] = field(default_factory=list)
    predicted_delta_p: float = 0.0   # Expected marginal progress
    risk_level: float = 1.0          # 1 (low) - 5 (critical detection risk)
    estimated_cost: float = 1.0      # Resource / time cost
    timestamp: float = field(default_factory=time.time)


@dataclass
class ProposalEvaluation:
    proposal_id: str
    strategist_id: str
    theoretical_accuracy: float     # 0 - 100 ("想得对不对")
    execution_success_rate: float   # 0 - 100 ("做得好不好")
    risk_reward_ratio: float        # 0 - 100 ("划不划算")
    marginal_delta_p: float         # Verified ΔP
    composite_score: float          # Final aggregated score
    rationale: str = ""


@dataclass
class LeadHandoverEvent:
    event_id: str
    round_number: int
    from_leader: str
    to_leader: str
    margin: float
    reason: str
    timestamp: float = field(default_factory=time.time)


@dataclass
class SubagentLootEvent:
    event_id: str
    round_number: int
    winner_id: str
    loser_id: str
    transferred_count: int = 1
    sanitized_experience: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


class CircuitBreakerState(str, Enum):
    NORMAL = "normal"
    STEALTH = "stealth"       # High stealth, passive observation
    BACKTRACK = "backtrack"   # Backtrack tree, discard saturated branches
    HUMAN_INTERVENTION = "human_intervention"


@dataclass
class TacticalCombatResult:
    combat_id: str
    round_number: int
    strategist_id: str
    target_node: str
    points_cost: int
    success: bool
    reward_points: int
    delta_p: float
    knowledge_references: List[str] = field(default_factory=list)
    action_log: List[str] = field(default_factory=list)
    lead_captured: bool = False
    timestamp: float = field(default_factory=time.time)
