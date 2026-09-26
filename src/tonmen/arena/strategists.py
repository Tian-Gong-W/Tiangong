from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Dict, List, Optional

from .models import TacticalProposal


class StrategistObserverPool:
    """Manages concurrent LLM Strategists observing the battlefield graph.

    Dispatches read-only graph snapshots and live security RAG context
    concurrently to 3~5 LLMs (Claude, DeepSeek, GPT, etc.), parsing and
    validating structured TacticalProposals for The Arbiter.
    """

    def __init__(self, profiles: Optional[List[Dict[str, Any]]] = None) -> None:
        self.profiles: List[Dict[str, Any]] = profiles or [
            {
                "id": "claude-3-5-sonnet",
                "name": "Claude 3.5 Sonnet",
                "model": "claude-3-5-sonnet-20241022",
                "format": "anthropic",
                "base_url": "https://api.anthropic.com",
                "api_key": "",
                "tactical_bias": "Heuristic state-space search & intent graphs",
            },
            {
                "id": "deepseek-v3",
                "name": "DeepSeek-V3",
                "model": "deepseek-chat",
                "format": "openai",
                "base_url": "https://api.deepseek.com/v1",
                "api_key": "",
                "tactical_bias": "Rapid conversion & pragmatic payload derivation",
            },
            {
                "id": "gpt-4o",
                "name": "GPT-4o",
                "model": "gpt-4o",
                "format": "openai",
                "base_url": "https://api.openai.com/v1",
                "api_key": "",
                "tactical_bias": "Broad asset perimeter & protocol edge-cases",
            },
        ]

    def add_profile(self, profile: Dict[str, Any]) -> None:
        self.profiles.append(profile)

    async def generate_proposals(
        self,
        graph_snapshot: Dict[str, Any],
        target_domain: str,
        knowledge_context: str = "",
        round_number: int = 1,
    ) -> List[TacticalProposal]:
        """Concurrently gathers proposals from all registered strategists."""
        tasks = [
            self._query_single_strategist(profile, graph_snapshot, target_domain, knowledge_context, round_number)
            for profile in self.profiles
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        valid_proposals: List[TacticalProposal] = []
        for res in results:
            if isinstance(res, TacticalProposal):
                valid_proposals.append(res)

        return valid_proposals

    async def _query_single_strategist(
        self,
        profile: Dict[str, Any],
        graph_snapshot: Dict[str, Any],
        target_domain: str,
        knowledge_context: str,
        round_number: int,
    ) -> TacticalProposal:
        s_id = profile["id"]
        api_key = profile.get("api_key", "").strip()
        format_type = profile.get("format", "openai")
        base_url = profile.get("base_url", "")
        model_name = profile.get("model", "")

        if not api_key:
            try:
                from tonmen.ai.secrets import get_secret
                if "deepseek" in s_id:
                    api_key = get_secret("DEEPSEEK_API_KEY")
                    base_url = "https://api.deepseek.com"
                    model_name = "deepseek-chat"
                    format_type = "openai"
                elif "claude" in s_id or "anthropic" in s_id:
                    api_key = get_secret("ANTHROPIC_API_KEY")
                    if not api_key:
                        openrouter_key = get_secret("OPENROUTER_API_KEY")
                        if openrouter_key:
                            api_key = openrouter_key
                            format_type = "openai"
                            base_url = "https://openrouter.ai/api/v1"
                            model_name = "nex-agi/nex-n2.5-pro:free"
                elif "gpt" in s_id or "openai" in s_id:
                    api_key = get_secret("OPENAI_API_KEY")
                    if not api_key:
                        openrouter_key = get_secret("OPENROUTER_API_KEY")
                        if openrouter_key:
                            api_key = openrouter_key
                            format_type = "openai"
                            base_url = "https://openrouter.ai/api/v1"
                            model_name = "nvidia/nemotron-3.5-lightning:free"
            except Exception:
                pass

        # If API key is configured, perform real HTTP call through transports with 10s ceiling
        if api_key:
            profile_with_key = dict(profile)
            profile_with_key["api_key"] = api_key
            profile_with_key["format"] = format_type
            profile_with_key["base_url"] = base_url
            profile_with_key["model"] = model_name
            try:
                proposal = await asyncio.wait_for(
                    self._call_real_transport(profile_with_key, graph_snapshot, target_domain, knowledge_context, round_number),
                    timeout=5.5,
                )
                if proposal:
                    return proposal
            except Exception:
                pass

        # Robust autonomous fallback heuristic proposal (ensures loop always operates without stalls)
        return self._generate_heuristic_proposal(profile, graph_snapshot, target_domain, round_number)

    async def _call_real_transport(
        self,
        profile: Dict[str, Any],
        graph_snapshot: Dict[str, Any],
        target_domain: str,
        knowledge_context: str,
        round_number: int,
    ) -> Optional[TacticalProposal]:
        from types import SimpleNamespace
        from tonmen.ai.transports import TRANSPORT_REGISTRY

        transport = TRANSPORT_REGISTRY.get(profile.get("format", "openai"))
        if not transport:
            return None

        # Build structural object expected by Transport implementations
        obj_profile = SimpleNamespace(
            id=profile.get("id"),
            name=profile.get("name", "Strategist"),
            model=profile.get("model", ""),
            base_url=profile.get("base_url", ""),
            api_key=profile.get("api_key", ""),
            format=profile.get("format", "openai"),
            rate_per_second=profile.get("rate_per_second", 0),
            rate_per_minute=profile.get("rate_per_minute", 0),
            max_tokens=profile.get("max_tokens", 2048),
            timeout_seconds=profile.get("timeout_seconds", 5),
        )

        system_prompt = (
            "You are a Lead Tactical Strategist in the Tiangong Cyber Arena. "
            "Analyze the read-only Attack Graph snapshot and formulate a high-confidence attack proposal. "
            "Output JSON with keys: hypothesis, target_id, preconditions (list), proposed_actions (list of dict), "
            "predicted_delta_p (float 0.0-1.0), risk_level (1-5), estimated_cost (1-5)."
        )

        user_payload = {
            "target": target_domain,
            "round": round_number,
            "graph_snapshot": graph_snapshot,
            "live_knowledge": knowledge_context,
            "bias": profile.get("tactical_bias", ""),
        }

        # Run synchronous transport call in threadpool
        loop = asyncio.get_running_loop()
        parsed_json, usage, _ = await loop.run_in_executor(
            None,
            lambda: transport.complete_json(obj_profile, system=system_prompt, payload=user_payload),
        )

        return TacticalProposal(
            proposal_id=f"prop-r{round_number}-{profile['id']}",
            strategist_id=profile["id"],
            hypothesis=str(parsed_json.get("hypothesis", f"Hypothesis from {profile.get('name')}")),
            target_id=str(parsed_json.get("target_id", target_domain)),
            preconditions=list(parsed_json.get("preconditions", [])),
            proposed_actions=list(parsed_json.get("proposed_actions", [{"action": "probe", "tool": "nuclei"}])),
            predicted_delta_p=float(parsed_json.get("predicted_delta_p", 0.2)),
            risk_level=float(parsed_json.get("risk_level", 2.0)),
            estimated_cost=float(parsed_json.get("estimated_cost", 1.5)),
        )

    def _generate_heuristic_proposal(
        self,
        profile: Dict[str, Any],
        graph_snapshot: Dict[str, Any],
        target_domain: str,
        round_number: int,
    ) -> TacticalProposal:
        """Generates specialized heuristic proposals based on model tactical bias."""
        s_id = profile["id"]

        if "claude" in s_id:
            hypothesis = f"Deconstruct authorization path on {target_domain} via multi-step token flow analysis"
            actions = [{"action": "jwt_inspect", "tool": "token_analyzer"}, {"action": "idor_test", "tool": "http_probe"}]
            risk = 1.5
            pred_delta = 0.25
        elif "deepseek" in s_id:
            hypothesis = f"Rapid surface penetration on {target_domain} checking parameter injection & unauthenticated endpoints"
            actions = [{"action": "sqli_probe", "tool": "nuclei"}, {"action": "bypass_verify", "tool": "http_probe"}]
            risk = 2.0
            pred_delta = 0.30
        else:
            hypothesis = f"Broad boundary reconnaissance on {target_domain} identifying subdomains and unmapped ports"
            actions = [{"action": "subdomain_enum", "tool": "subfinder"}, {"action": "port_probe", "tool": "katana"}]
            risk = 1.0
            pred_delta = 0.15

        return TacticalProposal(
            proposal_id=f"prop-r{round_number}-{s_id}",
            strategist_id=s_id,
            hypothesis=hypothesis,
            target_id=target_domain,
            preconditions=["recon_info"],
            proposed_actions=actions,
            predicted_delta_p=pred_delta,
            risk_level=risk,
            estimated_cost=1.2,
        )
