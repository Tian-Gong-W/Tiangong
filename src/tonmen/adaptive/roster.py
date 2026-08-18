from __future__ import annotations

from dataclasses import dataclass

from tonmen.missions import MissionPlan, MissionRun

from .confidence import assess_evidence_confidence
from .model import TargetProfile, build_target_profile


@dataclass(frozen=True, slots=True)
class AgentAssignment:
    role: str
    focus: str


_BASE_ROLES = (
    AgentAssignment("evidence_verifier", "evidence_integrity"),
    AgentAssignment("governance_reviewer", "scope_policy_budget"),
    AgentAssignment("remediation_editor", "remediation_and_residual_risk"),
)


def select_agent_roster(
    plan: MissionPlan,
    run: MissionRun,
    *,
    min_agents: int = 3,
    preferred_agents: int = 4,
    max_agents: int = 5,
) -> tuple[AgentAssignment, ...]:
    if not 3 <= min_agents <= preferred_agents <= max_agents <= 5:
        raise ValueError("agent roster must stay within 3-5 agents")

    profile = build_target_profile(plan, run)
    confidence = assess_evidence_confidence(plan, run)
    candidates: list[AgentAssignment] = []

    if confidence.conflicted:
        candidates.append(AgentAssignment("conflict_analyst", "evidence_conflict_and_corroboration"))
    if profile.ports or "network_surface" in profile.unknowns:
        candidates.append(AgentAssignment("network_surface_mapper", "network_and_service_surface"))
    if profile.has_web_surface or profile.target_kind == "web":
        candidates.append(AgentAssignment("web_surface_analyst", "web_routes_technology_and_api_surface"))
    if "api_surface" in {item.key for item in profile.hypotheses}:
        candidates.append(AgentAssignment("api_analyst", "api_contract_auth_and_input_surface"))
    if profile.findings:
        candidates.append(AgentAssignment("vulnerability_analyst", "finding_validation_and_risk"))
    if profile.severe_findings:
        candidates.append(AgentAssignment("impact_analyst", "impact_preconditions_and_attack_path"))
    if any("remediation" in item for item in profile.unknowns):
        candidates.append(AgentAssignment("remediation_editor", "remediation_and_residual_risk"))

    existing = {item.role for item in candidates}
    for role in _BASE_ROLES:
        if role.role not in existing:
            candidates.append(role)
            existing.add(role.role)

    desired = preferred_agents
    if profile.complexity <= 1:
        desired = min_agents
    elif profile.complexity >= 4 or confidence.conflicted:
        desired = max_agents
    desired = max(min_agents, min(max_agents, desired))
    return tuple(candidates[:desired])


def desired_assessment_rounds(
    profile: TargetProfile,
    *,
    minimum: int = 7,
    preferred: int = 8,
    maximum: int = 10,
) -> int:
    if not 7 <= minimum <= preferred <= maximum <= 10:
        raise ValueError("assessment rounds must stay within 7-10")

    rounds = preferred
    if profile.complexity <= 1 and not profile.findings:
        rounds = minimum
    if profile.complexity >= 4:
        rounds += 1
    if profile.severe_findings:
        rounds += 1
    return max(minimum, min(maximum, rounds))
