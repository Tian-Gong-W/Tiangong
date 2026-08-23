from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from tonmen.adaptive import build_target_profile
from tonmen.ai import AIProviderError
from tonmen.capabilities import CapabilityCandidate, CapabilityCatalog
from tonmen.core.runtime import TonmenRuntime
from tonmen.evidence import GraphNode
from tonmen.missions import MissionPlan, MissionRun, MissionRunState, MissionStep

from .planner import MissionPlanner

_AI_TIEBREAK_WINDOW = 5.0
_AI_MAX_ADJUSTMENT = 2.5


@dataclass(frozen=True, slots=True)
class PlanExpansion:
    """One evidence-backed capability addition; never an executable shell proposal."""

    step: MissionStep
    rationale: str
    expected_information_gain: str
    basis_fact_ids: tuple[str, ...]
    profile_unknowns: tuple[str, ...]
    deterministic_score: float = 0.0
    score_reasons: tuple[str, ...] = ()
    candidate_rankings: tuple[dict[str, Any], ...] = ()
    final_score: float = 0.0
    ai_tiebreak_applied: bool = False
    ai_preference: float = 0.0
    ai_adjustment: float = 0.0
    ai_rationale: str = ""
    selection_engine: str = "capability_catalog"


class AdaptiveMissionPlanner:
    """Grow a mission one governed semantic capability at a time from evidence.

    Registered ToolSpecs declare prerequisites, information gain and planning cost.
    CapabilityCatalog remains the deterministic authority. Optional local AI may only
    provide bounded preference signals among already-eligible candidates whose base
    scores are within a narrow tie-break window. AI cannot alter eligibility, risk,
    readiness, Scope, Policy, Approval, parameters or REPORT_ONLY.
    """

    def __init__(self, runtime: TonmenRuntime) -> None:
        self.runtime = runtime
        self.base = MissionPlanner(runtime)
        self.catalog = CapabilityCatalog(runtime)

    def seed(self, target: str) -> MissionPlan:
        return self.base.seed(target)

    @staticmethod
    def _ai_snapshot(run: MissionRun) -> tuple[str, ...]:
        return tuple(item.id for item in run.evidence[-16:])

    @staticmethod
    def _preference_payload(advisory) -> list[dict[str, Any]]:
        return [
            {
                "tool": item.tool,
                "preference": float(item.preference),
                "rationale": item.rationale,
                "basis_fact_ids": list(item.basis_fact_ids),
            }
            for item in getattr(advisory, "capability_preferences", ())
        ]

    @staticmethod
    def _preferences_from_metadata(metadata: dict[str, Any]) -> dict[str, dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        for item in metadata.get("capability_preferences", ()):
            if not isinstance(item, dict) or not item.get("tool"):
                continue
            try:
                preference = max(-1.0, min(1.0, float(item.get("preference", 0.0))))
            except (TypeError, ValueError):
                preference = 0.0
            result[str(item["tool"])] = {
                "preference": preference,
                "rationale": str(item.get("rationale") or "")[:800],
                "basis_fact_ids": tuple(str(value) for value in item.get("basis_fact_ids", ()))[:16],
            }
        return result

    def _record_local_ai_advisory(
        self,
        plan: MissionPlan,
        run: MissionRun,
        rankings: tuple[CapabilityCandidate, ...] = (),
    ) -> dict[str, dict[str, Any]]:
        service = self.runtime.ai
        if service is None or not service.enabled or not run.evidence:
            return {}
        evidence_ids = self._ai_snapshot(run)
        for node in run.graph.nodes.values():
            if (
                node.kind in {"ai.advisory", "ai.advisory_error"}
                and tuple(node.metadata.get("evidence_ids", ())) == evidence_ids
            ):
                if node.kind == "ai.advisory":
                    return self._preferences_from_metadata(dict(node.metadata))
                return {}

        candidate_context = tuple(
            item.audit_payload()
            for item in rankings[:8]
            if item.eligible
        )
        try:
            try:
                advisory = service.advise(plan, run, candidates=candidate_context)
            except TypeError as exc:
                # Compatibility for injected test/local services written before the
                # optional candidates keyword existed. Do not mask unrelated TypeError.
                if "candidates" not in str(exc):
                    raise
                advisory = service.advise(plan, run)
        except (AIProviderError, ValueError, OSError) as exc:
            node_id = uuid4().hex
            run.graph.add_node(
                GraphNode(
                    id=node_id,
                    kind="ai.advisory_error",
                    label="local AI advisory unavailable; deterministic fallback retained",
                    metadata={
                        "provider": self.runtime.config.ai_provider,
                        "model": self.runtime.config.ai_model,
                        "error": str(exc)[:600],
                        "evidence_ids": list(evidence_ids),
                        "candidate_tools": [item["tool"] for item in candidate_context],
                        "execution_authority": False,
                        "local_only": True,
                        "fallback": "deterministic",
                    },
                )
            )
            run.graph.link(run.id, "ai_fallback", node_id)
            if self.runtime.events is not None:
                self.runtime.events.publish(
                    "ai.advisory_failed",
                    mission_id=run.id,
                    plan_id=run.plan_id,
                    target=run.target,
                    provider=self.runtime.config.ai_provider,
                    model=self.runtime.config.ai_model,
                    error=str(exc)[:600],
                    deterministic_fallback=True,
                )
            return {}

        if advisory is None:
            return {}
        node_id = uuid4().hex
        hypotheses = [
            {
                "key": item.key,
                "summary": item.summary,
                "confidence": item.confidence,
                "basis_fact_ids": list(item.basis_fact_ids),
            }
            for item in advisory.hypotheses
        ]
        preferences = self._preference_payload(advisory)
        allowed_tools = {item["tool"] for item in candidate_context}
        preferences = [item for item in preferences if item["tool"] in allowed_tools]
        run.graph.add_node(
            GraphNode(
                id=node_id,
                kind="ai.advisory",
                label=advisory.summary or "local AI evidence advisory",
                metadata={
                    "provider": advisory.provider,
                    "model": advisory.model,
                    "phase": "pre_reasoning_advisory",
                    "summary": advisory.summary,
                    "focus": list(advisory.focus),
                    "hypotheses": hypotheses,
                    "challenge_decision": advisory.challenge_decision,
                    "challenge_reason": advisory.challenge_reason,
                    "basis_fact_ids": list(advisory.basis_fact_ids),
                    "evidence_ids": list(evidence_ids),
                    "candidate_tools": sorted(allowed_tools),
                    "capability_preferences": preferences,
                    "preference_authority": "bounded_tiebreak_only",
                    "execution_authority": False,
                    "local_only": advisory.local_only,
                    "api_key_required": False,
                },
            )
        )
        run.graph.link(run.id, "advised_by", node_id)
        for fact_id in advisory.basis_fact_ids:
            if fact_id in run.graph.nodes:
                run.graph.link(fact_id, "supports_ai_advisory", node_id)
        if self.runtime.events is not None:
            self.runtime.events.publish(
                "ai.advisory",
                mission_id=run.id,
                plan_id=run.plan_id,
                target=run.target,
                advisory_id=node_id,
                provider=advisory.provider,
                model=advisory.model,
                summary=advisory.summary,
                focus=list(advisory.focus),
                basis_fact_ids=list(advisory.basis_fact_ids),
                candidate_tools=sorted(allowed_tools),
                capability_preferences=preferences,
                challenge_decision=advisory.challenge_decision,
                execution_authority=False,
                local_only=True,
            )
        return self._preferences_from_metadata({"capability_preferences": preferences})

    @staticmethod
    def _select_candidate(
        rankings: tuple[CapabilityCandidate, ...],
        preferences: dict[str, dict[str, Any]],
    ) -> tuple[CapabilityCandidate | None, tuple[dict[str, Any], ...], dict[str, Any]]:
        eligible = [item for item in rankings if item.eligible]
        if not eligible:
            return None, tuple(item.audit_payload() for item in rankings[:8]), {
                "applied": False,
                "selection_engine": "capability_catalog",
            }

        deterministic_top = eligible[0]
        rows: list[dict[str, Any]] = []
        final_scores: dict[str, float] = {}
        for item in rankings[:8]:
            row = item.audit_payload()
            pref = preferences.get(item.tool, {}) if item.eligible else {}
            preference = max(-1.0, min(1.0, float(pref.get("preference", 0.0)))) if pref else 0.0
            within_window = bool(
                item.eligible
                and deterministic_top.score - item.score <= _AI_TIEBREAK_WINDOW
            )
            adjustment = round(preference * _AI_MAX_ADJUSTMENT, 3) if within_window else 0.0
            final_score = round(item.score + adjustment, 3)
            final_scores[item.tool] = final_score
            row.update(
                {
                    "ai_preference": preference,
                    "ai_adjustment": adjustment,
                    "ai_rationale": str(pref.get("rationale") or "")[:800] if pref else "",
                    "within_ai_tiebreak_window": within_window,
                    "final_score": final_score,
                }
            )
            rows.append(row)

        selected = max(
            eligible,
            key=lambda item: (final_scores.get(item.tool, item.score), item.score, item.tool),
        )
        selected_pref = preferences.get(selected.tool, {})
        selected_adjustment = round(
            final_scores.get(selected.tool, selected.score) - selected.score,
            3,
        )
        changed = selected.tool != deterministic_top.tool
        any_adjustment = any(abs(float(row.get("ai_adjustment", 0.0))) > 0 for row in rows)
        return selected, tuple(rows), {
            "applied": any_adjustment,
            "changed_selection": changed,
            "deterministic_winner": deterministic_top.tool,
            "selected_tool": selected.tool,
            "preference": float(selected_pref.get("preference", 0.0)) if selected_pref else 0.0,
            "adjustment": selected_adjustment,
            "rationale": str(selected_pref.get("rationale") or "")[:800] if selected_pref else "",
            "final_score": final_scores.get(selected.tool, selected.score),
            "selection_engine": "capability_catalog+bounded_ai_tiebreak" if any_adjustment else "capability_catalog",
            "tiebreak_window": _AI_TIEBREAK_WINDOW,
            "max_adjustment": _AI_MAX_ADJUSTMENT,
        }

    def _build(
        self,
        plan: MissionPlan,
        run: MissionRun,
        candidate: CapabilityCandidate,
        ranking_rows: tuple[dict[str, Any], ...],
        ai_result: dict[str, Any],
    ) -> PlanExpansion:
        step = self.base.build_step(
            candidate.tool,
            plan.target,
            parameters=candidate.parameters,
            rationale=candidate.rationale,
        )
        profile = build_target_profile(plan, run)
        return PlanExpansion(
            step=step,
            rationale=candidate.rationale,
            expected_information_gain=candidate.expected_information_gain,
            basis_fact_ids=candidate.basis_fact_ids,
            profile_unknowns=tuple(profile.unknowns),
            deterministic_score=candidate.score,
            score_reasons=candidate.reasons,
            candidate_rankings=ranking_rows,
            final_score=float(ai_result.get("final_score", candidate.score)),
            ai_tiebreak_applied=bool(ai_result.get("applied", False)),
            ai_preference=float(ai_result.get("preference", 0.0)),
            ai_adjustment=float(ai_result.get("adjustment", 0.0)),
            ai_rationale=str(ai_result.get("rationale") or ""),
            selection_engine=str(ai_result.get("selection_engine") or "capability_catalog"),
        )

    def propose(self, plan: MissionPlan, run: MissionRun) -> PlanExpansion | None:
        if run.plan_id != plan.id:
            raise ValueError("mission run does not belong to this plan")
        if run.state in {MissionRunState.FAILED, MissionRunState.DENIED, MissionRunState.WAITING_APPROVAL}:
            return None

        rankings = self.catalog.rank(plan, run)
        if not any(item.eligible for item in rankings):
            self._record_local_ai_advisory(plan, run, rankings)
            return None
        preferences = self._record_local_ai_advisory(plan, run, rankings)
        candidate, ranking_rows, ai_result = self._select_candidate(rankings, preferences)
        if candidate is None:
            return None
        return self._build(plan, run, candidate, ranking_rows, ai_result)

    def apply(self, plan: MissionPlan, run: MissionRun, proposal: PlanExpansion) -> MissionPlan:
        """Append a proposal to immutable plan history and mutable run state."""
        revised = plan.extend([proposal.step])
        execution = run.append_planned_step(proposal.step)

        if proposal.step.id not in run.graph.nodes:
            run.graph.add_node(
                GraphNode(
                    id=proposal.step.id,
                    kind="step",
                    label=f"{proposal.step.tool}:{proposal.step.target}",
                    metadata={
                        "risk": proposal.step.risk,
                        "requires_approval": proposal.step.requires_approval,
                        "adaptive": True,
                    },
                )
            )
            run.graph.link(run.id, "contains", proposal.step.id)

        revision_id = uuid4().hex
        run.graph.add_node(
            GraphNode(
                id=revision_id,
                kind="planning.revision",
                label=f"adaptive plan + {proposal.step.tool}",
                metadata={
                    "tool": proposal.step.tool,
                    "target": proposal.step.target,
                    "risk": proposal.step.risk,
                    "requires_approval": proposal.step.requires_approval,
                    "rationale": proposal.rationale,
                    "expected_information_gain": proposal.expected_information_gain,
                    "basis_fact_ids": list(proposal.basis_fact_ids),
                    "profile_unknowns": list(proposal.profile_unknowns),
                    "deterministic_score": proposal.deterministic_score,
                    "final_score": proposal.final_score,
                    "score_reasons": list(proposal.score_reasons),
                    "candidate_rankings": list(proposal.candidate_rankings),
                    "ai_tiebreak": {
                        "applied": proposal.ai_tiebreak_applied,
                        "preference": proposal.ai_preference,
                        "adjustment": proposal.ai_adjustment,
                        "rationale": proposal.ai_rationale,
                        "window": _AI_TIEBREAK_WINDOW,
                        "max_adjustment": _AI_MAX_ADJUSTMENT,
                        "execution_authority": False,
                    },
                    "selection_engine": proposal.selection_engine,
                    "execution_authority": False,
                },
            )
        )
        run.graph.link(run.id, "replanned_by", revision_id)
        run.graph.link(revision_id, "adds_step", proposal.step.id)
        for fact_id in proposal.basis_fact_ids:
            if fact_id in run.graph.nodes:
                run.graph.link(fact_id, "supports_plan_revision", revision_id)

        execution.metadata["plan_revision_id"] = revision_id
        execution.metadata["plan_rationale"] = proposal.rationale
        execution.metadata["expected_information_gain"] = proposal.expected_information_gain
        execution.metadata["basis_fact_ids"] = list(proposal.basis_fact_ids)
        execution.metadata["deterministic_score"] = proposal.deterministic_score
        execution.metadata["final_score"] = proposal.final_score
        execution.metadata["selection_engine"] = proposal.selection_engine
        execution.metadata["ai_tiebreak_applied"] = proposal.ai_tiebreak_applied

        if self.runtime.events is not None:
            self.runtime.events.publish(
                "plan.revised",
                mission_id=run.id,
                plan_id=run.plan_id,
                target=run.target,
                revision_id=revision_id,
                step_id=proposal.step.id,
                tool=proposal.step.tool,
                step_target=proposal.step.target,
                risk=proposal.step.risk,
                requires_approval=proposal.step.requires_approval,
                rationale=proposal.rationale,
                expected_information_gain=proposal.expected_information_gain,
                deterministic_score=proposal.deterministic_score,
                final_score=proposal.final_score,
                score_reasons=list(proposal.score_reasons),
                ai_tiebreak_applied=proposal.ai_tiebreak_applied,
                ai_adjustment=proposal.ai_adjustment,
                selection_engine=proposal.selection_engine,
                basis_fact_ids=list(proposal.basis_fact_ids),
            )
        return revised
