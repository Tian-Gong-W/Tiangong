from __future__ import annotations

from typing import Any

from tonmen.missions import MissionPlan, MissionRun, MissionStep, StepExecutionState
from tonmen.tools import ToolRegistry, ToolRequest
from tonmen.tools.adapters import register_builtin_adapters

from .model import TargetProfile, build_target_profile


class AdaptiveParameterResolver:
    """Resolve bounded execution parameters through typed adapter declarations.

    Central adaptation is tool-name agnostic. Semantic prerequisites come from
    ToolSpec.planning and profile-aware parameter tuning belongs to each ToolAdapter.
    Scope, risk, approval, tool identity and target remain immutable here.

    Runtime plugin adapters are adapted and validated by CapabilityCatalog before a
    dynamic step is committed. If this standalone/default resolver does not contain
    that plugin adapter, it preserves those catalog-validated step parameters; the
    real runtime adapter and Executor still perform final typed validation and Policy.
    """

    def __init__(self, registry: ToolRegistry | None = None) -> None:
        if registry is None:
            registry = ToolRegistry()
            register_builtin_adapters(registry)
        self.registry = registry

    def profile(self, plan: MissionPlan, run: MissionRun) -> TargetProfile:
        return build_target_profile(plan, run)

    def _completed_capabilities(self, plan: MissionPlan, run: MissionRun) -> set[str]:
        planned = {step.id: step for step in plan.steps}
        capabilities: set[str] = set()
        for execution in run.steps:
            if execution.state not in {StepExecutionState.SUCCEEDED, StepExecutionState.DEGRADED}:
                continue
            step = planned.get(execution.step_id)
            if step is None or step.tool not in self.registry:
                continue
            capabilities.update(self.registry.get(step.tool).spec.capabilities)
        return capabilities

    def justify(self, plan: MissionPlan, run: MissionRun, step: MissionStep) -> tuple[bool, str]:
        profile = self.profile(plan, run)
        if step.tool not in self.registry:
            return True, "runtime plugin prerequisites were validated by CapabilityCatalog"
        adapter = self.registry.get(step.tool)
        planning = adapter.spec.planning
        if planning is None:
            return True, "adapter has no adaptive prerequisites"

        missing_profile = [
            requirement
            for requirement in planning.requires_profile
            if not requirement or requirement.startswith("_") or not bool(getattr(profile, requirement, False))
        ]
        if missing_profile:
            return False, "profile prerequisites missing: " + ", ".join(missing_profile)

        completed = self._completed_capabilities(plan, run)
        missing_capabilities = [
            requirement
            for requirement in planning.requires_capabilities
            if requirement not in completed
        ]
        if missing_capabilities:
            return False, "semantic prerequisites missing: " + ", ".join(missing_capabilities)

        return True, "declared semantic prerequisites are satisfied by the current target profile"

    @staticmethod
    def _context(profile: TargetProfile) -> dict[str, Any]:
        return {
            "target_kind": profile.target_kind,
            "complexity": profile.complexity,
            "port_count": len(profile.ports),
            "service_count": len(profile.services),
            "web_url_count": len(profile.web_urls),
            "technology_count": len(profile.technologies),
            "finding_count": len(profile.findings),
            "severe_findings": profile.severe_findings,
            "unknowns": tuple(profile.unknowns),
            "hypotheses": tuple(item.key for item in profile.hypotheses),
        }

    def resolve(self, plan: MissionPlan, run: MissionRun, step: MissionStep) -> dict[str, Any]:
        profile = self.profile(plan, run)
        if step.tool not in self.registry:
            return dict(step.parameters)
        adapter = self.registry.get(step.tool)
        request = ToolRequest(tool=step.tool, target=step.target, parameters=dict(step.parameters))
        resolved = dict(adapter.adapt_parameters(request, self._context(profile)))
        adapter.validate(ToolRequest(tool=step.tool, target=step.target, parameters=resolved))
        return resolved
