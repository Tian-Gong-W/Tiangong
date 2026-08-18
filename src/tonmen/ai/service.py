from __future__ import annotations

from dataclasses import replace
from typing import Any

from tonmen.adaptive import assess_evidence_confidence, build_target_profile
from tonmen.core.config import TonmenConfig
from tonmen.missions import MissionPlan, MissionRun
from tonmen.reasoning import ReasoningDecision

from .model import AIAdvisory, AIProviderStatus
from .ollama import OllamaProvider


class LocalAIService:
    """Optional local advisory layer. It never owns execution authority."""

    def __init__(self, config: TonmenConfig) -> None:
        self.config = config
        self.provider: OllamaProvider | None = None
        if config.ai_enabled and config.ai_provider == "ollama":
            self.provider = OllamaProvider(
                base_url=config.ai_base_url,
                model=config.ai_model,
                timeout_seconds=config.ai_timeout_seconds,
            )

    @property
    def enabled(self) -> bool:
        return self.provider is not None

    def status(self) -> AIProviderStatus:
        if self.provider is None:
            return AIProviderStatus(
                enabled=False,
                provider=self.config.ai_provider,
                model=self.config.ai_model,
                ready=False,
                code="disabled",
                detail="local AI is disabled; deterministic TONMEN logic remains active",
            )
        return self.provider.status()

    @staticmethod
    def _fact_payload(run: MissionRun) -> tuple[list[dict[str, Any]], set[str]]:
        nodes = [node for node in run.graph.nodes.values() if node.kind.startswith("intelligence.")]
        nodes = nodes[-64:]
        fact_ids = {node.id for node in nodes}
        facts = [
            {
                "id": node.id,
                "kind": node.kind,
                "label": node.label,
                "source": node.metadata.get("source"),
                "severity": node.metadata.get("severity"),
                "confidence": node.metadata.get("confidence"),
            }
            for node in nodes
        ]
        return facts, fact_ids

    @staticmethod
    def _candidate_payload(candidates: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None) -> list[dict[str, Any]]:
        safe: list[dict[str, Any]] = []
        for item in list(candidates or ())[:8]:
            if not isinstance(item, dict) or not item.get("tool"):
                continue
            safe.append(
                {
                    "tool": str(item.get("tool"))[:128],
                    "deterministic_score": float(item.get("score", 0.0)),
                    "reasons": [str(value)[:300] for value in list(item.get("reasons", ()))[:8]],
                    "provides": [str(value)[:128] for value in list(item.get("provides", ()))[:16]],
                    "requires_capabilities": [str(value)[:128] for value in list(item.get("requires_capabilities", ()))[:16]],
                    "resolves_unknowns": [str(value)[:128] for value in list(item.get("resolves_unknowns", ()))[:16]],
                    "risk": int(item.get("risk", 0)),
                    "requires_approval": bool(item.get("requires_approval", False)),
                    "eligible": bool(item.get("eligible", True)),
                    "execution_authority": False,
                }
            )
        return safe

    def _context(
        self,
        plan: MissionPlan,
        run: MissionRun,
        decision: ReasoningDecision | None,
        candidates: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None,
    ) -> tuple[dict[str, Any], set[str], set[str]]:
        profile = build_target_profile(plan, run)
        confidence = assess_evidence_confidence(plan, run)
        facts, fact_ids = self._fact_payload(run)
        candidate_payload = self._candidate_payload(candidates)
        allowed_candidate_tools = {
            item["tool"] for item in candidate_payload if item.get("eligible") is True
        }
        decision_payload = None
        if decision is not None:
            decision_payload = {
                "id": decision.id,
                "action": decision.action.value,
                "summary": decision.summary,
                "basis_fact_ids": list(decision.basis_fact_ids),
                "next_step_id": decision.next_step_id,
                "requires_human": decision.requires_human,
            }
        context = {
            "governance": {
                "execution_authority": False,
                "scope_expansion": False,
                "approval_authority": False,
                "arbitrary_shell": False,
                "report_only": True,
                "candidate_preferences_are_tiebreak_only": True,
            },
            "phase": "decision_review" if decision is not None else "pre_reasoning_advisory",
            "target": plan.target,
            "mission_state": run.state.value,
            "target_profile": {
                "kind": profile.target_kind,
                "complexity": profile.complexity,
                "ports": list(profile.ports),
                "services": list(profile.services),
                "dns_addresses": list(profile.dns_addresses[:16]),
                "tls_versions": list(profile.tls_versions[:8]),
                "certificate_sans": list(profile.certificate_sans[:32]),
                "web_urls": list(profile.web_urls[:32]),
                "technologies": list(profile.technologies[:32]),
                "api_endpoints": list(profile.api_endpoints[:32]),
                "api_hints": list(profile.api_hints[:16]),
                "api_inspected": profile.api_inspected,
                "unknowns": list(profile.unknowns),
                "hypotheses": [
                    {
                        "key": item.key,
                        "summary": item.summary,
                        "confidence": item.confidence,
                        "basis_fact_ids": list(item.basis_fact_ids),
                    }
                    for item in profile.hypotheses
                ],
            },
            "evidence_confidence": [
                {
                    "key": item.key,
                    "subject": item.subject,
                    "assertion": item.assertion,
                    "state": item.state.value,
                    "confidence": item.confidence,
                    "sources": list(item.sources),
                    "observed_values": list(item.observed_values),
                    "support_fact_ids": list(item.support_fact_ids),
                    "conflict_fact_ids": list(item.conflict_fact_ids),
                }
                for item in confidence.claims
            ],
            "planned_capabilities": [
                {
                    "step_id": step.id,
                    "tool": step.tool,
                    "risk": step.risk,
                    "requires_approval": step.requires_approval,
                    "state": execution.state.value,
                }
                for step, execution in zip(plan.steps, run.steps, strict=True)
            ],
            "catalog_candidates": candidate_payload,
            "deterministic_decision": decision_payload,
            "facts": facts,
        }
        return context, fact_ids, allowed_candidate_tools

    def advise(
        self,
        plan: MissionPlan,
        run: MissionRun,
        decision: ReasoningDecision | None = None,
        *,
        candidates: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None = None,
    ) -> AIAdvisory | None:
        if self.provider is None:
            return None
        context, fact_ids, candidate_tools = self._context(plan, run, decision, candidates)
        if candidate_tools:
            advisory = self.provider.advise(
                context,
                allowed_fact_ids=fact_ids,
                allowed_candidate_tools=candidate_tools,
            )
        else:
            advisory = self.provider.advise(context, allowed_fact_ids=fact_ids)
        if decision is None and (advisory.challenge_decision or advisory.challenge_reason):
            advisory = replace(advisory, challenge_decision=False, challenge_reason="")
        return advisory
