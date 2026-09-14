from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from tonmen.arena.arbiter import TheArbiter
from tonmen.arena.graph import ProbabilisticAttackGraph
from tonmen.arena.models import LootCategory, LootItem, TacticalProposal
from tonmen.arena.arbiter import TheArbiter
from tonmen.arena.graph import ProbabilisticAttackGraph
from tonmen.arena.models import LootCategory, LootItem, TacticalProposal
from tonmen.evidence import EvidenceRecord
from tonmen.missions import MissionRun

logger = logging.getLogger(__name__)


class MissionArenaBridge:
    """Connects real mission telemetry and tool execution to the Arbiter & PAG.

    Maps real-world scan/exploit evidence into state nodes:
      - Host/IP discovery, port discovery -> recon_info
      - WAF / CDN detected -> waf_identified
      - WAF rule bypass / 200 OK evasion -> waf_bypassed
      - CVE / Nuclei / vulnerability finding -> service_vuln
      - Foothold / token / DB access -> foothold_access
      - High privilege / root / data dump -> target_admin
    """

    def __init__(self, arbiter: TheArbiter) -> None:
        self.arbiter = arbiter

    def sync_mission_evidence(self, run: MissionRun) -> Dict[str, Any]:
        """Inspects mission evidence, maps to graph nodes, and triggers Arbiter evaluation."""
        unlocked = []
        highest_category = LootCategory.INFO

        for item in run.evidence:
            data_str = (item.stdout + " " + " ".join(item.argv)).lower()
            tool = item.tool.lower()

            if "admin" in data_str or "root" in data_str or "database dump" in data_str or "flag" in data_str:
                unlocked.append("target_admin")
                highest_category = LootCategory.ADMIN
            elif "sqli" in tool or "sqli" in data_str or "token" in data_str or "foothold" in data_str or "injection" in data_str:
                unlocked.append("foothold_access")
                highest_category = LootCategory.ACCESS
            elif "vuln" in data_str or "cve-" in data_str or "nuclei" in tool or "finding" in data_str:
                unlocked.append("service_vuln")
                if highest_category in {LootCategory.INFO, LootCategory.BYPASS}:
                    highest_category = LootCategory.BYPASS
            elif "waf" in tool or "waf" in data_str or "cloudflare" in data_str:
                unlocked.append("waf_identified")
            elif "port" in tool or "nmap" in tool or "httpx" in tool or "open" in data_str:
                unlocked.append("recon_info")

        # Deduplicate and keep unachieved nodes
        new_nodes = [n for n in set(unlocked) if n not in self.arbiter.graph.achieved_nodes]
        
        # Build proposals for active strategists
        current_leader = self.arbiter.ledger.current_leader_id or "claude-3-5-sonnet"
        proposals = []
        results = {}

        for s_id in self.arbiter.ledger.strategists.keys():
            prop_id = f"prop-mission-{run.id[:8]}-{s_id}"
            is_lead = (s_id == current_leader)
            
            # Leader has highest alignment with mission direction
            proposals.append(
                TacticalProposal(
                    proposal_id=prop_id,
                    strategist_id=s_id,
                    hypothesis=f"Real target mission progression ({run.target})",
                    target_id=run.target,
                    preconditions=["recon_info"] if "recon_info" in self.arbiter.graph.achieved_nodes else [],
                    proposed_actions=[{"tool": "mission_executor", "target": run.target}],
                    risk_level=2.0 if is_lead else 3.0,
                    estimated_cost=1.5,
                )
            )

            # Settle actual results
            results[prop_id] = {
                "successful_actions_count": len(run.evidence) if is_lead else max(1, len(run.evidence) - 1),
                "unlocked_nodes": new_nodes if is_lead else (new_nodes[:1] if new_nodes else []),
                "loot_category": highest_category,
            }

        return self.arbiter.evaluate_round(proposals, results)
