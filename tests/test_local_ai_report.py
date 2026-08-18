from __future__ import annotations

from tonmen.evidence import GraphNode
from tonmen.missions import MissionPlan, MissionRun
from tonmen.reports import ReportStore


def test_reports_persist_local_ai_advisory_as_non_authoritative_provenance(tmp_path):
    plan = MissionPlan.create("localhost", [])
    run = MissionRun.create(plan)
    run.graph.add_node(
        GraphNode(
            id="ai-1",
            kind="ai.advisory",
            label="Local advisory summary",
            metadata={
                "provider": "ollama",
                "model": "test-model",
                "summary": "Local advisory summary",
                "focus": ["corroborate web evidence"],
                "hypotheses": [{"key": "h1", "summary": "review", "confidence": 0.7, "basis_fact_ids": []}],
                "basis_fact_ids": [],
                "challenge_decision": False,
                "challenge_reason": "",
                "local_only": True,
                "api_key_required": False,
                "execution_authority": False,
            },
        )
    )
    store = ReportStore(tmp_path)

    report = store.save(plan, run)
    persisted = store.load_json(run.id)
    markdown = store.load_markdown(run.id)

    assert report["summary"]["ai_advisories"] == 1
    assert report["summary"]["ai_advisory_errors"] == 0
    assert persisted["ai_advisories"][0]["kind"] == "ai.advisory"
    assert persisted["ai_advisories"][0]["metadata"]["execution_authority"] is False
    assert persisted["ai_advisories"][0]["metadata"]["api_key_required"] is False
    assert "## Local AI Advisory" in markdown
    assert "API key required by TONMEN: no" in markdown
    assert "Execution authority: none" in markdown
    assert "test-model" in markdown


def test_reports_persist_local_ai_failure_as_deterministic_fallback(tmp_path):
    plan = MissionPlan.create("localhost", [])
    run = MissionRun.create(plan)
    run.graph.add_node(
        GraphNode(
            id="ai-error-1",
            kind="ai.advisory_error",
            label="local AI advisory unavailable; deterministic fallback retained",
            metadata={
                "provider": "ollama",
                "model": "test-model",
                "error": "provider unavailable",
                "fallback": "deterministic",
                "local_only": True,
                "execution_authority": False,
            },
        )
    )
    store = ReportStore(tmp_path)

    report = store.save(plan, run)
    markdown = store.load_markdown(run.id)

    assert report["summary"]["ai_advisories"] == 0
    assert report["summary"]["ai_advisory_errors"] == 1
    assert "deterministic fallback" in markdown
    assert "provider unavailable" in markdown
