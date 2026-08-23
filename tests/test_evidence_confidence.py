from __future__ import annotations

from tonmen.adaptive import ClaimState, assess_evidence_confidence, select_agent_roster
from tonmen.evidence import GraphNode
from tonmen.missions import MissionPlan, MissionRun
from tonmen.reasoning import MissionReasoner, ReasoningAction


def _run_with_conflicting_web_status():
    plan = MissionPlan.create("https://localhost", [])
    run = MissionRun.create(plan)
    run.graph.add_node(
        GraphNode(
            id="httpx-web",
            kind="intelligence.web",
            label="https://localhost/ [200]",
            metadata={
                "source": "httpx",
                "target": "https://localhost/",
                "confidence": 1.0,
                "data": {"url": "https://localhost/", "status_code": 200},
            },
        )
    )
    run.graph.add_node(
        GraphNode(
            id="crawler-web",
            kind="intelligence.web",
            label="https://localhost/ [503]",
            metadata={
                "source": "crawler",
                "target": "https://localhost/",
                "confidence": 1.0,
                "data": {"url": "https://localhost/", "status_code": 503},
            },
        )
    )
    return plan, run


def test_comparable_fact_disagreement_becomes_explicit_conflict():
    plan, run = _run_with_conflicting_web_status()

    assessment = assess_evidence_confidence(plan, run)
    status = next(item for item in assessment.claims if item.key == "web_status:https://localhost/")

    assert status.state is ClaimState.CONFLICTED
    assert set(status.observed_values) == {"200", "503"}
    assert status.support_fact_ids
    assert status.conflict_fact_ids
    assert set(status.sources) == {"httpx", "crawler"}
    assert 0.0 < status.confidence < 1.0


def test_absence_of_api_evidence_is_unresolved_not_conflicting():
    plan, run = _run_with_conflicting_web_status()

    assessment = assess_evidence_confidence(plan, run)
    api = next(item for item in assessment.claims if item.key == "api_surface")

    assert api.state is ClaimState.UNRESOLVED
    assert not api.conflict_fact_ids


def test_conflict_routes_a_specialist_into_bounded_council_roster():
    plan, run = _run_with_conflicting_web_status()

    roster = select_agent_roster(plan, run)

    assert 3 <= len(roster) <= 5
    assert roster[0].role == "conflict_analyst"


def test_reasoner_reviews_conflict_before_declaring_convergence():
    plan, run = _run_with_conflicting_web_status()

    decision = MissionReasoner().decide(plan, run)

    assert decision.action is ReasoningAction.REVIEW
    assert decision.requires_human is True
    assert "evidence conflict" in decision.summary.lower()
    assert set(decision.basis_fact_ids) == {"httpx-web", "crawler-web"}
