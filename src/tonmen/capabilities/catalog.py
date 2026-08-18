from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from tonmen.adaptive import build_target_profile
from tonmen.core.runtime import TonmenRuntime
from tonmen.missions import MissionPlan, MissionRun, StepExecutionState
from tonmen.policy import Decision
from tonmen.tools import ToolRequest


@dataclass(frozen=True, slots=True)
class CapabilityCandidate:
    """One catalog evaluation. It is a planning record, never execution authority."""

    tool: str
    target: str
    parameters: dict[str, Any]
    eligible: bool
    score: float
    rationale: str
    expected_information_gain: str
    basis_fact_ids: tuple[str, ...]
    reasons: tuple[str, ...]
    provides: tuple[str, ...]
    requires_capabilities: tuple[str, ...]
    resolves_unknowns: tuple[str, ...]
    risk: int
    requires_approval: bool
    readiness_code: str
    execution_authority: bool = False

    def audit_payload(self) -> dict[str, Any]:
        return {
            "tool": self.tool,
            "eligible": self.eligible,
            "score": self.score,
            "reasons": list(self.reasons),
            "provides": list(self.provides),
            "requires_capabilities": list(self.requires_capabilities),
            "resolves_unknowns": list(self.resolves_unknowns),
            "risk": self.risk,
            "requires_approval": self.requires_approval,
            "readiness_code": self.readiness_code,
            "execution_authority": False,
        }


def target_kind(target: str) -> str:
    parsed = urlparse(target if "://" in target else f"scheme://{target}")
    return "web" if parsed.scheme in {"http", "https"} else "host"


class CapabilityCatalog:
    """Registry-backed capability discovery and deterministic candidate scoring.

    Tool-specific prerequisites live on ToolSpec.planning. The catalog evaluates those
    declarations against the live Target Profile, completed semantic capabilities,
    readiness and Policy. It does not contain a fixed tool sequence and cannot execute.
    """

    def __init__(self, runtime: TonmenRuntime) -> None:
        self.runtime = runtime

    @staticmethod
    def _successful_state(state: StepExecutionState) -> bool:
        return state in {StepExecutionState.SUCCEEDED, StepExecutionState.DEGRADED}

    def completed_capabilities(self, plan: MissionPlan, run: MissionRun) -> set[str]:
        planned = {step.id: step for step in plan.steps}
        capabilities: set[str] = set()
        for execution in run.steps:
            if not self._successful_state(execution.state):
                continue
            step = planned.get(execution.step_id)
            if step is None or step.tool not in self.runtime.registry:
                continue
            capabilities.update(self.runtime.registry.get(step.tool).spec.capabilities)
        return capabilities

    @staticmethod
    def _basis_fact_ids(run: MissionRun, kinds: tuple[str, ...]) -> tuple[str, ...]:
        if not kinds:
            return ()
        wanted = set(kinds)
        return tuple(
            node.id
            for node in run.graph.nodes.values()
            if node.kind in wanted
        )[:16]

    @staticmethod
    def _profile_requirement(profile, requirement: str) -> bool:
        if not requirement or requirement.startswith("_"):
            return False
        return bool(getattr(profile, requirement, False))

    @staticmethod
    def _profile_context(profile) -> dict[str, Any]:
        return {
            "target_kind": profile.target_kind,
            "complexity": profile.complexity,
            "ports": tuple(profile.ports),
            "services": tuple(profile.services),
            "dns_addresses": tuple(profile.dns_addresses),
            "tls_versions": tuple(profile.tls_versions),
            "port_count": len(profile.ports),
            "service_count": len(profile.services),
            "web_url_count": len(profile.web_urls),
            "technology_count": len(profile.technologies),
            "finding_count": len(profile.findings),
            "severe_findings": profile.severe_findings,
            "unknowns": tuple(profile.unknowns),
            "hypotheses": tuple(item.key for item in profile.hypotheses),
        }

    @staticmethod
    def _target_for_mode(target: str, mode: str) -> str:
        if mode != "host":
            return target
        parsed = urlparse(target if "://" in target else f"scheme://{target}")
        if not parsed.hostname:
            raise ValueError("target has no hostname")
        return parsed.hostname

    def _readiness(self, adapter) -> tuple[bool, str]:
        if self.runtime.executor is not None and not self.runtime.executor.uses_local_subprocess:
            return True, "injected_executor"
        readiness = adapter.readiness()
        return readiness.ready, readiness.code

    def seed_tools(self, target: str) -> tuple[str, ...]:
        kind = target_kind(target)
        ranked: list[tuple[float, str]] = []
        for adapter in self.runtime.registry:
            planning = adapter.spec.planning
            if planning is None or kind not in planning.seed_for:
                continue
            score = (
                float(planning.information_gain_score) * 100.0
                - float(adapter.spec.risk) * 6.0
                - float(planning.cost_score) * 20.0
            )
            ranked.append((score, adapter.spec.name))
        return tuple(name for _, name in sorted(ranked, key=lambda item: (-item[0], item[1])))

    def envelope_tools(self, target: str) -> tuple[str, ...]:
        _ = target_kind(target)
        return tuple(
            adapter.spec.name
            for adapter in self.runtime.registry
            if adapter.spec.planning is not None
        )

    def evaluate(self, plan: MissionPlan, run: MissionRun, tool: str, *, require_ready: bool = True) -> CapabilityCandidate:
        if run.plan_id != plan.id:
            raise ValueError("mission run does not belong to this plan")
        adapter = self.runtime.registry.get(tool)
        spec = adapter.spec
        planning = spec.planning
        if planning is None:
            return CapabilityCandidate(
                tool=spec.name,
                target=plan.target,
                parameters={},
                eligible=False,
                score=-1000.0,
                rationale=spec.description,
                expected_information_gain="",
                basis_fact_ids=(),
                reasons=("no adaptive planning metadata",),
                provides=tuple(spec.capabilities),
                requires_capabilities=(),
                resolves_unknowns=(),
                risk=int(spec.risk),
                requires_approval=False,
                readiness_code="unknown",
            )

        profile = build_target_profile(plan, run)
        kind = target_kind(plan.target)
        completed = self.completed_capabilities(plan, run)
        queued = {step.tool for step in plan.steps}
        reasons: list[str] = []
        eligible = True

        if spec.name in queued:
            eligible = False
            reasons.append("already queued in mission plan")
        if kind not in planning.target_kinds:
            eligible = False
            reasons.append(f"target kind {kind} is not supported")

        missing_profile = tuple(
            requirement
            for requirement in planning.requires_profile
            if not self._profile_requirement(profile, requirement)
        )
        if missing_profile:
            eligible = False
            reasons.append("profile prerequisites missing: " + ", ".join(missing_profile))

        missing_capabilities = tuple(
            requirement
            for requirement in planning.requires_capabilities
            if requirement not in completed
        )
        if missing_capabilities:
            eligible = False
            reasons.append("semantic prerequisites missing: " + ", ".join(missing_capabilities))

        step_target = self._target_for_mode(plan.target, planning.target_mode)
        parameters = dict(planning.default_parameters)
        request = ToolRequest(tool=spec.name, target=step_target, parameters=parameters)
        requires_approval = False
        try:
            parameters = dict(adapter.adapt_parameters(request, self._profile_context(profile)))
            request = ToolRequest(tool=spec.name, target=step_target, parameters=parameters)
            adapter.validate(request)
            policy = self.runtime.policy.evaluate(spec, request)
            requires_approval = policy.decision is Decision.REQUIRE_APPROVAL
            if policy.decision is Decision.DENY:
                eligible = False
                reasons.append("policy denied candidate: " + policy.reason)
        except (TypeError, ValueError) as exc:
            eligible = False
            reasons.append("typed adapter rejected candidate: " + str(exc))

        ready, readiness_code = self._readiness(adapter)
        if require_ready and not ready:
            eligible = False
            reasons.append("tool is not ready: " + readiness_code)

        unresolved = set(profile.unknowns)
        resolution_hits = [item for item in planning.resolves_unknowns if item in unresolved]
        novel_capabilities = [item for item in spec.capabilities if item not in completed]
        score = float(planning.information_gain_score) * 100.0
        score += min(18.0, len(resolution_hits) * 6.0)
        score += min(10.0, len(novel_capabilities) * 2.0)
        score += min(5.0, float(profile.complexity))
        score -= float(spec.risk) * 6.0
        score -= float(planning.cost_score) * 20.0
        if requires_approval:
            score -= 8.0
        if not ready:
            score -= 15.0
        if not eligible:
            score -= 1000.0
        score = round(score, 3)

        if resolution_hits:
            reasons.append("closes unknowns: " + ", ".join(resolution_hits))
        if novel_capabilities:
            reasons.append("adds semantic capabilities: " + ", ".join(novel_capabilities))
        reasons.append(f"deterministic score={score:.3f}")

        return CapabilityCandidate(
            tool=spec.name,
            target=step_target,
            parameters=parameters,
            eligible=eligible,
            score=score,
            rationale=planning.rationale or spec.description,
            expected_information_gain=planning.information_gain,
            basis_fact_ids=self._basis_fact_ids(run, planning.basis_fact_kinds),
            reasons=tuple(reasons),
            provides=tuple(spec.capabilities),
            requires_capabilities=tuple(planning.requires_capabilities),
            resolves_unknowns=tuple(planning.resolves_unknowns),
            risk=int(spec.risk),
            requires_approval=requires_approval,
            readiness_code=readiness_code,
        )

    def rank(self, plan: MissionPlan, run: MissionRun, *, require_ready: bool = True) -> tuple[CapabilityCandidate, ...]:
        candidates = [
            self.evaluate(plan, run, adapter.spec.name, require_ready=require_ready)
            for adapter in self.runtime.registry
            if adapter.spec.planning is not None
        ]
        candidates.sort(key=lambda item: (-int(item.eligible), -item.score, item.tool))
        return tuple(candidates)

    def next_candidate(self, plan: MissionPlan, run: MissionRun) -> CapabilityCandidate | None:
        return next((item for item in self.rank(plan, run) if item.eligible), None)
