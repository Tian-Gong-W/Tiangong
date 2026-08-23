from __future__ import annotations

from urllib.parse import urlparse

from tonmen.capabilities import CapabilityCatalog
from tonmen.core.runtime import TonmenRuntime
from tonmen.missions import MissionPlan, MissionStep
from tonmen.policy import Decision
from tonmen.tools import ToolRequest


class MissionPlanningDenied(RuntimeError):
    pass


def _target_for_mode(target: str, mode: str) -> str:
    if mode != "host":
        return target
    parsed = urlparse(target if "://" in target else f"scheme://{target}")
    if not parsed.hostname:
        raise MissionPlanningDenied("target has no hostname")
    return parsed.hostname


class MissionPlanner:
    """Build governed candidate plans or minimal adaptive seeds. It never executes tools."""

    def __init__(self, runtime: TonmenRuntime) -> None:
        self.runtime = runtime
        self.catalog = CapabilityCatalog(runtime)

    def _require_scope(self, target: str) -> None:
        if self.runtime.scope is None or not self.runtime.scope.is_allowed(target):
            raise MissionPlanningDenied("target is outside the authorized scope")

    def build_step(
        self,
        tool: str,
        target: str,
        *,
        parameters: dict | None = None,
        rationale: str | None = None,
    ) -> MissionStep:
        self._require_scope(target)
        try:
            adapter = self.runtime.registry.get(tool)
        except KeyError as exc:
            raise MissionPlanningDenied(str(exc)) from exc

        planning = adapter.spec.planning
        mode = planning.target_mode if planning is not None else "as_is"
        step_target = _target_for_mode(target, mode)
        defaults = dict(planning.default_parameters) if planning is not None else {}
        resolved = dict(defaults if parameters is None else parameters)
        request = ToolRequest(tool=adapter.spec.name, target=step_target, parameters=resolved)
        adapter.validate(request)
        decision = self.runtime.policy.evaluate(adapter.spec, request)
        if decision.decision is Decision.DENY:
            raise MissionPlanningDenied(f"{adapter.spec.name}: {decision.reason}")
        default_rationale = planning.rationale if planning is not None else adapter.spec.description
        return MissionStep.create(
            tool=adapter.spec.name,
            target=step_target,
            parameters=resolved,
            risk=int(adapter.spec.risk),
            requires_approval=decision.decision is Decision.REQUIRE_APPROVAL,
            rationale=rationale or default_rationale or adapter.spec.description,
        )

    def seed(self, target: str) -> MissionPlan:
        self._require_scope(target)
        candidates = self.catalog.seed_tools(target)
        if not candidates:
            raise MissionPlanningDenied("no registered seed capability supports this target kind")
        failures: list[str] = []
        for tool in candidates:
            try:
                return MissionPlan.create(target, [self.build_step(tool, target)])
            except (MissionPlanningDenied, ValueError) as exc:
                failures.append(f"{tool}: {exc}")
        raise MissionPlanningDenied("no governed seed capability could be materialized: " + "; ".join(failures))

    def plan(self, target: str, *, include_adaptive_only: bool = False) -> MissionPlan:
        """Return a dry-run capability envelope, never an execution order.

        The default keeps the historical baseline envelope stable for callers that still
        exercise it directly. Operator preview may request the full adaptive pool, while
        MissionLoop always starts from `seed()` and uses live Catalog ranking.
        """
        self._require_scope(target)
        steps: list[MissionStep] = []
        for tool in self.catalog.envelope_tools(target, include_adaptive_only=include_adaptive_only):
            try:
                step = self.build_step(tool, target)
            except (MissionPlanningDenied, ValueError):
                continue
            steps.append(step)
        return MissionPlan.create(target, steps)
