from __future__ import annotations

from datetime import datetime, timezone

from tonmen.evidence import EvidenceRecord, GraphNode
from tonmen.missions import MissionPlan, MissionRun, MissionStep
from tonmen.reports import build_report, render_markdown


def _adaptive_report_fixture():
    seed = MissionStep.create(
        tool="httpx",
        target="https://example.test",
        parameters={"timeout": 10, "follow_redirects": False},
        risk=1,
        requires_approval=False,
        rationale="seed",
    )
    dynamic = MissionStep.create(
        tool="crawler",
        target="https://example.test",
        parameters={"max_pages": 25, "max_depth": 2, "timeout": 10},
        risk=1,
        requires_approval=False,
        rationale="dynamic crawler",
    )
    plan = MissionPlan.create("https://example.test", [seed, dynamic])
    run = MissionRun.create(plan)
    revision_id = "rev1"
    fact_id = "fact1"
    evidence_id = "ev1"
    reasoning_id = "reason1"
    round_id = "round1"
    agent_id = "agent1"

    run.steps[1].metadata.update(
        {
            "plan_revision_id": revision_id,
            "basis_fact_ids": [fact_id],
            "adaptive_profile": {
                "kind": "web",
                "complexity": 2,
                "unknowns": ["same_origin_endpoint_coverage"],
                "hypotheses": ["web_surface"],
            },
        }
    )

    now = datetime.now(timezone.utc)
    run.evidence.append(
        EvidenceRecord(
            id=evidence_id,
            tool="httpx",
            target="https://example.test",
            argv=("httpx", "-u", "https://example.test"),
            exit_code=0,
            stdout="https://example.test [200] [Example] [nginx]\n",
            stderr="",
            started_at=now,
            finished_at=now,
        )
    )

    for node in (
        GraphNode(id=evidence_id, kind="evidence", label="evidence:httpx"),
        GraphNode(id=fact_id, kind="intelligence.web", label="https://example.test [200] Example"),
        GraphNode(id=dynamic.id, kind="step", label="crawler:https://example.test"),
        GraphNode(
            id=revision_id,
            kind="planning.revision",
            label="adaptive plan + crawler",
            metadata={
                "tool": "crawler",
                "basis_fact_ids": [fact_id],
                "rationale": "HTTP evidence confirms a Web surface; add bounded same-origin endpoint coverage.",
                "expected_information_gain": "same-origin pages, routes and page metadata",
                "execution_authority": False,
            },
        ),
        GraphNode(
            id=reasoning_id,
            kind="reasoning.continue",
            label="Continue with crawler",
            metadata={"action": "continue", "basis_fact_ids": [fact_id], "next_step_id": dynamic.id},
        ),
        GraphNode(
            id=round_id,
            kind="council.round",
            label="assessment round 2: web_surface",
            metadata={"round": 2, "focus": "web_surface", "decision_id": reasoning_id},
        ),
        GraphNode(
            id=agent_id,
            kind="council.subagent",
            label="web_surface_analyst",
            metadata={"role": "web_surface_analyst", "fact_ids": [fact_id], "execution_authority": False},
        ),
    ):
        run.graph.add_node(node)

    run.graph.link(evidence_id, "reveals", fact_id)
    run.graph.link(fact_id, "supports_plan_revision", revision_id)
    run.graph.link(revision_id, "adds_step", dynamic.id)
    run.graph.link(round_id, "contains_subagent", agent_id)
    return plan, run, revision_id, fact_id, evidence_id, reasoning_id, round_id, dynamic.id


def test_report_persists_adaptive_why_graph_causality():
    plan, run, revision_id, fact_id, evidence_id, reasoning_id, round_id, step_id = _adaptive_report_fixture()

    report = build_report(plan, run)

    assert report["summary"]["adaptive_revisions"] == 1
    assert len(report["adaptive_causality"]) == 1
    chain = report["adaptive_causality"][0]
    assert chain["step_id"] == step_id
    assert chain["tool"] == "crawler"
    assert chain["revision"]["id"] == revision_id
    assert chain["basis_fact_ids"] == [fact_id]
    assert chain["basis_facts"][0]["id"] == fact_id
    assert chain["evidence"][0]["id"] == evidence_id
    assert chain["reasoning"][0]["id"] == reasoning_id
    assert chain["council"][0]["id"] == round_id
    assert chain["support_edges"] == 1
    assert chain["adds_step_edge"] is True
    assert chain["execution_authority"] is False
    assert chain["expected_information_gain"] == "same-origin pages, routes and page metadata"


def test_markdown_report_explains_why_dynamic_tool_was_selected():
    plan, run, *_ = _adaptive_report_fixture()

    markdown = render_markdown(build_report(plan, run))

    assert "## Adaptive Causality / Why Graph" in markdown
    assert "Why 1: crawler" in markdown
    assert "HTTP evidence confirms a Web surface" in markdown
    assert "same-origin pages, routes and page metadata" in markdown
    assert "Support edges: `1`" in markdown
    assert "Revision adds step edge: `True`" in markdown
    assert "Execution authority: `False`" in markdown
