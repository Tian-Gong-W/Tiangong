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


class MissionPlanner:
    """Deterministic planner over governed capabilities. It never executes tools."""

    def __init__(self, runtime: TonmenRuntime) -> None:
        self.runtime = runtime

    def plan(self, target: str) -> MissionPlan:
        if self.runtime.scope is None or not self.runtime.scope.is_allowed(target):
            raise MissionPlanningDenied("target is outside the authorized scope")

        defaults = {
            "nmap": {"ports": "80,443", "service_detection": True},
            "httpx": {"follow_redirects": False, "timeout": 10},
            "nuclei": {"severity": ("medium", "high", "critical"), "rate_limit": 10, "timeout": 10},
        }
        rationales = {
            "nmap": "Establish a minimal network/service view on common web ports.",
            "httpx": "Collect HTTP status, title and technology metadata.",
            "nuclei": "Validate higher-confidence web findings only after explicit approval.",
        }
        order = {"nmap": 10, "httpx": 20, "nuclei": 30}
        steps: list[MissionStep] = []

        for adapter in sorted(self.runtime.registry, key=lambda item: order.get(item.spec.name, 100)):
            step_target = _host_target(target) if adapter.spec.name == "nmap" else target
            parameters = defaults.get(adapter.spec.name, {})
            request = ToolRequest(tool=adapter.spec.name, target=step_target, parameters=parameters)
            adapter.validate(request)
            decision = self.runtime.policy.evaluate(adapter.spec, request)
            if decision.decision is Decision.DENY:
                continue
            requires_approval = decision.decision is Decision.REQUIRE_APPROVAL
            steps.append(
                MissionStep.create(
                    tool=adapter.spec.name,
                    target=step_target,
                    parameters=parameters,
                    risk=int(adapter.spec.risk),
                    requires_approval=requires_approval,
                    rationale=rationales.get(adapter.spec.name, adapter.spec.description),
                )
            )

        return MissionPlan.create(target, steps)
