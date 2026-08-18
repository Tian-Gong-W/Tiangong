from __future__ import annotations

from tonmen.evidence import GraphNode
from tonmen.missions import MissionPlan, MissionRun
from tonmen.reports import ReportStore


def test_report_persists_capability_ranking_and_bounded_ai_tiebreak(tmp_path):
    plan = MissionPlan.create("localhost", [])
    run = MissionRun.create(plan)
    run.graph.add_node(GraphNode(id=run.id, kind="mission", label="mission", metadata={"plan_id": plan.id}))
    run.graph.add_node(
        GraphNode(
            id="revision-1",
            kind="planning.revision",
            label="adaptive plan + alternate",
            metadata={
                "tool": "alternate",
                "target": "localhost",
                "deterministic_score": 77.0,
                "final_score": 79.5,
                "selection_engine": "capability_catalog+bounded_ai_tiebreak",
                "score_reasons": ["adds semantic capabilities: demo.observe"],
                "candidate_rankings": [
                    {
                        "tool": "base",
                        "eligible": True,
                        "score": 80.0,
                        "ai_adjustment": -2.5,
                        "final_score": 77.5,
                        "reasons": ["deterministic score=80.000"],
                    },
                    {
                        "tool": "alternate",
                        "eligible": True,
                        "score": 77.0,
                        "ai_adjustment": 2.5,
                        "final_score": 79.5,
                        "reasons": ["deterministic score=77.000"],
                    },
                    {
                        "tool": "blocked",
                        "eligible": False,
                        "score": -900.0,
                        "ai_adjustment": 0.0,
                        "final_score": -900.0,
                        "reasons": ["policy denied candidate"],
                    },
                ],
                "ai_tiebreak": {
                    "applied": True,
                    "preference": 1.0,
                    "adjustment": 2.5,
                    "rationale": "closes the current uncertainty",
                    "execution_authority": False,
                },
                "execution_authority": False,
            },
        )
    )
    run.graph.link(run.id, "replanned_by", "revision-1")

    store = ReportStore(tmp_path)
    report = store.save(plan, run)
    markdown = store.load_markdown(run.id)

    selection = report["capability_selection"][0]
    assert selection["tool"] == "alternate"
    assert selection["deterministic_score"] == 77.0
    assert selection["final_score"] == 79.5
    assert selection["ai_tiebreak"]["applied"] is True
    assert selection["candidate_rankings"][2]["eligible"] is False
    assert report["summary"]["ai_tiebreak_selections"] == 1
    assert "## Capability Selection Audit" in markdown
    assert "capability_catalog+bounded_ai_tiebreak" in markdown
    assert "policy denied candidate" in markdown
    assert "Execution authority: none" in markdown
