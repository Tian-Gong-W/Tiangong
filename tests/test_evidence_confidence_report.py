from __future__ import annotations

from tonmen.evidence import GraphNode
from tonmen.missions import MissionPlan, MissionRun
from tonmen.reports import ReportStore


def _conflicted_run():
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


def test_report_store_persists_structured_evidence_confidence(tmp_path):
    plan, run = _conflicted_run()
    store = ReportStore(tmp_path)

    report = store.save(plan, run)
    persisted = store.load_json(run.id)

    assert report["summary"]["conflicted_claims"] == 1
    assert persisted["evidence_confidence"]["conflicted"] == 1
    claim = next(
        item
        for item in persisted["evidence_confidence"]["claims"]
        if item["key"] == "web_status:https://localhost/"
    )
    assert claim["state"] == "conflicted"
    assert set(claim["observed_values"]) == {"200", "503"}
    assert claim["support_fact_ids"]
    assert claim["conflict_fact_ids"]
    assert set(claim["sources"]) == {"httpx", "crawler"}


def test_markdown_report_includes_conflict_posture(tmp_path):
    plan, run = _conflicted_run()
    store = ReportStore(tmp_path)

    store.save(plan, run)
    markdown = store.load_markdown(run.id)

    assert "## Evidence Confidence / Conflict" in markdown
    assert "Conflicted claims: 1" in markdown
    assert "absence of evidence is not treated as contradictory evidence" in markdown
    assert "HTTP status https://localhost/" in markdown
    assert "**conflicted**" in markdown
