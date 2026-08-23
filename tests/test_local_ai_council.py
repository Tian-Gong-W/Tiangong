from __future__ import annotations

from tonmen.council import AssessmentCouncil
from tonmen.evidence import GraphNode
from tonmen.missions import MissionPlan, MissionRun


def test_council_routes_local_ai_advisory_to_read_only_reviewer():
    plan = MissionPlan.create("localhost", [])
    run = MissionRun.create(plan)
    run.graph.add_node(GraphNode(id=run.id, kind="mission", label="mission:localhost", metadata={"plan_id": plan.id}))
    run.graph.add_node(
        GraphNode(
            id="fact-1",
            kind="intelligence.web",
            label="http://localhost [200]",
            metadata={
                "source": "httpx",
                "target": "http://localhost",
                "confidence": 1.0,
                "severity": "info",
                "data": {"url": "http://localhost", "status_code": 200},
            },
        )
    )
    run.graph.add_node(
        GraphNode(
            id="ai-1",
            kind="ai.advisory",
            label="Review the web evidence.",
            metadata={
                "provider": "ollama",
                "model": "test-model",
                "basis_fact_ids": ["fact-1"],
                "hypotheses": [{"key": "h1", "summary": "review", "confidence": 0.7, "basis_fact_ids": ["fact-1"]}],
                "challenge_decision": True,
                "execution_authority": False,
                "local_only": True,
            },
        )
    )

    council = AssessmentCouncil()
    round_id = council.record_round(plan, run, session_id="session-1", phase="live")

    assert round_id is not None
    round_node = run.graph.nodes[round_id]
    assert 3 <= round_node.metadata["agents"] <= 5
    assert "ai_advisory_reviewer" in round_node.metadata["roles"]
    assert round_node.metadata["local_ai_advisory"]["id"] == "ai-1"
    assert round_node.metadata["local_ai_advisory"]["execution_authority"] is False

    reviewer_edges = [
        edge
        for edge in run.graph.edges
        if edge.source == round_id and edge.relation == "contains_subagent"
    ]
    reviewers = [run.graph.nodes[edge.target] for edge in reviewer_edges]
    ai_reviewer = next(node for node in reviewers if node.metadata.get("role") == "ai_advisory_reviewer")
    assert ai_reviewer.metadata["execution_authority"] is False
    assert ai_reviewer.metadata["report_only"] is True
    assert ai_reviewer.metadata["fact_ids"] == ["fact-1"]
    assert any(edge.source == "ai-1" and edge.relation == "reviewed_in" and edge.target == round_id for edge in run.graph.edges)
    assert any(edge.source == "ai-1" and edge.relation == "reviewed_by" and edge.target == ai_reviewer.id for edge in run.graph.edges)
