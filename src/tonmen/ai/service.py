from __future__ import annotations

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

    def _context(self, plan: MissionPlan, run: MissionRun, decision: ReasoningDecision) -> tuple[dict[str, Any], set[str]]:
        profile = build_target_profile(plan, run)
        confidence = assess_evidence_confidence(plan, run)
        facts, fact_ids = self._fact_payload(run)
        context = {
            "governance": {
                "execution_authority": False,
                "scope_expansion": False,
                "approval_authority": False,
                "arbitrary_shell": False,
                "report_only": True,
            },
            "target": plan.target,
            "mission_state": run.state.value,
            "target_profile": {
                "kind": profile.target_kind,
                "complexity": profile.complexity,
                "ports": list(profile.ports),
                "services": list(profile.services),
                "technologies": list(profile.technologies),
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
            "deterministic_decision": {
                "id": decision.id,
                "action": decision.action.value,
                "summary": decision.summary,
                "basis_fact_ids": list(decision.basis_fact_ids),
                "next_step_id": decision.next_step_id,
                "requires_human": decision.requires_human,
            },
            "facts": facts,
        }
        return context, fact_ids

    def advise(self, plan: MissionPlan, run: MissionRun, decision: ReasoningDecision) -> AIAdvisory | None:
        if self.provider is None:
            return None
        context, fact_ids = self._context(plan, run, decision)
        return self.provider.advise(context, allowed_fact_ids=fact_ids)
