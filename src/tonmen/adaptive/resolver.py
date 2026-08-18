from __future__ import annotations

from typing import Any

from tonmen.missions import MissionPlan, MissionRun, MissionStep, StepExecutionState

from .model import TargetProfile, build_target_profile


class AdaptiveParameterResolver:
    """Resolve bounded execution parameters and evidence-based branch justification.

    Planned parameters are safe seeds. Resolution may vary cost and coverage within
    adapter validation limits, but it never changes Scope, risk, approval, tool identity,
    or target.
    """

    def profile(self, plan: MissionPlan, run: MissionRun) -> TargetProfile:
        return build_target_profile(plan, run)

    @staticmethod
    def _completed_tools(run: MissionRun) -> set[str]:
        return {
            step.tool
            for step in run.steps
            if step.state in {
                StepExecutionState.SUCCEEDED,
                StepExecutionState.DEGRADED,
                StepExecutionState.SKIPPED,
            }
        }

    def justify(self, plan: MissionPlan, run: MissionRun, step: MissionStep) -> tuple[bool, str]:
        profile = self.profile(plan, run)
        completed = self._completed_tools(run)

        if step.tool == "httpx" and "nmap" in completed and profile.target_kind != "web":
            if profile.services and not any("http" in service for service in profile.services):
                return False, "network evidence does not show an HTTP-capable service"

        if step.tool == "crawler" and "httpx" in completed:
            if not profile.has_web_surface:
                return False, "HTTP observation did not establish an evidence-backed web surface"

        if step.tool == "nuclei":
            if not profile.has_web_surface:
                return False, "current evidence does not justify a web validation branch"

        return True, "candidate capability is justified by the current target profile"

    def resolve(self, plan: MissionPlan, run: MissionRun, step: MissionStep) -> dict[str, Any]:
        parameters = dict(step.parameters)
        profile = self.profile(plan, run)

        if step.tool == "httpx":
            parameters["timeout"] = max(5, min(20, 6 + profile.complexity * 2))
            parameters["follow_redirects"] = False

        elif step.tool == "crawler":
            observed_pages = max(1, len(profile.web_urls))
            adaptive_pages = 12 + profile.complexity * 8 + min(24, observed_pages * 2)
            parameters["max_pages"] = max(12, min(60, adaptive_pages))
            parameters["max_depth"] = max(1, min(4, 1 + profile.complexity // 2))
            parameters["timeout"] = max(5, min(20, 6 + profile.complexity * 2))

        elif step.tool == "nuclei":
            parameters["rate_limit"] = 6 if profile.complexity >= 4 else 10
            parameters["timeout"] = max(5, min(20, 6 + profile.complexity * 2))
            parameters.setdefault("severity", ("medium", "high", "critical"))

        return parameters
