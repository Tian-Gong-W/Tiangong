from __future__ import annotations

from urllib.parse import urlparse

from tonmen.core.runtime import TonmenRuntime
from tonmen.missions import MissionPlan, MissionStep
from tonmen.policy import Decision
from tonmen.tools import ToolRequest


class MissionPlanningDenied(RuntimeError):
    pass


def _host_target(target: str) -> str:
    parsed = urlparse(target if "://" in target else f"scheme://{target}")
    if not parsed.hostname:
        raise MissionPlanningDenied("target has no hostname")
    return parsed.hostname


_DEFAULTS = {
    "nmap": {"ports": "80,443", "service_detection": False},
    "httpx": {"follow_redirects": False, "timeout": 10},
    "crawler": {"max_pages": 25, "max_depth": 2, "timeout": 10},
    "nuclei": {"severity": ("medium", "high", "critical"), "rate_limit": 10, "timeout": 10},
}

_RATIONALES = {
    "nmap": "Establish a minimal TCP reachability view on common web ports without version probing.",
    "httpx": "Collect HTTP status, title and technology metadata.",
    "crawler": "Discover same-origin pages and endpoints with bounded depth and page budgets.",
    "nuclei": "Validate higher-confidence web findings only after explicit approval.",
}

_ORDER = {"nmap": 10, "httpx": 20, "crawler": 25, "nuclei": 30}


class MissionPlanner:
    """Build governed candidate plans or minimal adaptive seeds. It never executes tools."""

    def __init__(self, runtime: TonmenRuntime) -> None:
        self.runtime = runtime

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
        """Materialize one typed governed step from a registry capability."""
        self._require_scope(target)
        try:
            adapter = self.runtime.registry.get(tool)
        except KeyError as exc:
            raise MissionPlanningDenied(str(exc)) from exc
        step_target = _host_target(target) if adapter.spec.name == "nmap" else target
        resolved = dict(_DEFAULTS.get(adapter.spec.name, {}) if parameters is None else parameters)
        request = ToolRequest(tool=adapter.spec.name, target=step_target, parameters=resolved)
        adapter.validate(request)
        decision = self.runtime.policy.evaluate(adapter.spec, request)
        if decision.decision is Decision.DENY:
            raise MissionPlanningDenied(f"{adapter.spec.name}: {decision.reason}")
        return MissionStep.create(
            tool=adapter.spec.name,
            target=step_target,
            parameters=resolved,
            risk=int(adapter.spec.risk),
            requires_approval=decision.decision is Decision.REQUIRE_APPROVAL,
            rationale=rationale or _RATIONALES.get(adapter.spec.name, adapter.spec.description),
        )

    def seed(self, target: str) -> MissionPlan:
        """Create only the first capability needed for evidence-driven replanning.

        Explicit HTTP(S) targets already identify the protocol family, so their seed is
        HTTP metadata discovery. Host/IP targets begin with a minimal network view. No
        later capability is committed until recorded evidence justifies it.
        """
        self._require_scope(target)
        parsed = urlparse(target if "://" in target else f"scheme://{target}")
        tool = "httpx" if parsed.scheme in {"http", "https"} else "nmap"
        return MissionPlan.create(target, [self.build_step(tool, target)])

    def plan(self, target: str) -> MissionPlan:
        """Return the full bounded candidate capability envelope for dry-run inspection.

        The autonomous MissionLoop uses :meth:`seed` and grows its actual plan from
        evidence. This envelope remains useful for operators who want to see every
        capability the current registry/policy could potentially place on the path.
        """
        self._require_scope(target)
        steps: list[MissionStep] = []
        for adapter in sorted(self.runtime.registry, key=lambda item: _ORDER.get(item.spec.name, 100)):
            try:
                step = self.build_step(adapter.spec.name, target)
            except MissionPlanningDenied:
                continue
            steps.append(step)
        return MissionPlan.create(target, steps)
