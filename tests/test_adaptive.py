from __future__ import annotations

from tonmen.adaptive import AdaptiveParameterResolver, build_target_profile, desired_assessment_rounds, select_agent_roster
from tonmen.evidence import GraphNode
from tonmen.missions import MissionPlan, MissionRun, MissionStep
from tonmen.policy import Decision, PolicyEngine
from tonmen.tools import RiskLevel, ToolRequest, ToolSpec


def _plan_and_run():
    steps = [
        MissionStep.create(
            tool="crawler",
            target="https://localhost",
            parameters={"max_pages": 25, "max_depth": 2, "timeout": 10},
            risk=int(RiskLevel.DISCOVERY),
            requires_approval=False,
            rationale="candidate web coverage",
        )
    ]
    plan = MissionPlan.create("https://localhost", steps)
    return plan, MissionRun.create(plan)


def test_profile_tracks_unknowns_and_hypotheses_from_live_graph():
    plan, run = _plan_and_run()
    run.graph.add_node(
        GraphNode(
            id="web-1",
            kind="intelligence.web",
            label="https://localhost/api",
            metadata={"data": {"url": "https://localhost/api", "technologies": ["nginx"]}},
        )
    )

    profile = build_target_profile(plan, run)

    assert profile.target_kind == "web"
    assert profile.web_urls == ("https://localhost/api",)
    assert "same_origin_endpoint_coverage" in profile.unknowns
    assert {item.key for item in profile.hypotheses} >= {"web_surface", "api_surface"}


def test_agent_roster_and_rounds_expand_only_inside_fixed_bounds():
    plan, run = _plan_and_run()
    sparse = build_target_profile(plan, run)
    sparse_roster = select_agent_roster(plan, run)

    assert 3 <= len(sparse_roster) <= 5
    assert 7 <= desired_assessment_rounds(sparse) <= 10

    run.graph.add_node(
        GraphNode(
            id="web-1",
            kind="intelligence.web",
            label="https://localhost/api",
            metadata={"data": {"url": "https://localhost/api", "technologies": ["nginx"]}},
        )
    )
    run.graph.add_node(
        GraphNode(
            id="finding-1",
            kind="intelligence.finding",
            label="high-confidence exposure",
            metadata={"severity": "high", "data": {}},
        )
    )

    rich = build_target_profile(plan, run)
    rich_roster = select_agent_roster(plan, run)
    rich_rounds = desired_assessment_rounds(rich)

    assert len(rich_roster) == 5
    assert rich_rounds == 10


def test_parameter_resolver_changes_cost_with_profile_but_stays_bounded():
    plan, run = _plan_and_run()
    resolver = AdaptiveParameterResolver()
    sparse = resolver.resolve(plan, run, plan.steps[0])

    for index in range(8):
        run.graph.add_node(
            GraphNode(
                id=f"web-{index}",
                kind="intelligence.web",
                label=f"https://localhost/page-{index}",
                metadata={"data": {"url": f"https://localhost/page-{index}"}},
            )
        )
    run.graph.add_node(
        GraphNode(
            id="finding-1",
            kind="intelligence.finding",
            label="review item",
            metadata={"severity": "high", "data": {}},
        )
    )
    rich = resolver.resolve(plan, run, plan.steps[0])

    assert rich["max_pages"] > sparse["max_pages"]
    assert 12 <= sparse["max_pages"] <= 60
    assert 12 <= rich["max_pages"] <= 60
    assert 1 <= rich["max_depth"] <= 4
    assert 5 <= rich["timeout"] <= 20


def test_report_only_policy_blocks_final_active_capability_even_at_low_risk():
    spec = ToolSpec(
        name="demo-final-action",
        category="validation",
        description="test-only capability",
        risk=RiskLevel.PASSIVE,
        capabilities=("payload.execute",),
    )
    request = ToolRequest(tool=spec.name, target="localhost")

    decision = PolicyEngine().evaluate(spec, request)

    assert decision.decision is Decision.DENY
    assert "report-only" in decision.reason
