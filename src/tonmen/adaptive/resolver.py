from __future__ import annotations

from typing import Any

from tonmen.missions import MissionPlan, MissionRun, MissionStep

from .model import TargetProfile, build_target_profile


class AdaptiveParameterResolver:
    """Resolve bounded execution parameters from current evidence.

    Planned parameters are safe seeds. Resolution may vary cost and coverage within
    adapter validation limits, but it never changes Scope, risk, approval, tool identity,
    or target.
    """

    def profile(self, plan: MissionPlan, run: MissionRun) -> TargetProfile:
        return build_target_profile(plan, run)

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
