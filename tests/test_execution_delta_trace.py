from __future__ import annotations

from importlib import resources


def test_execution_delta_trace_links_tool_evidence_profile_and_replan():
    js = resources.files("tonmen.dashboard.static").joinpath("reports.js").read_text(encoding="utf-8")

    assert "Execution Delta · 工具级因果链" in js
    assert "Facts produced" in js
    assert "Unknowns closed" in js
    assert "Unknowns opened" in js
    assert "Hypotheses +" in js
    assert "Hypotheses −" in js
    assert "因此下一步" in js
    assert "expected_information_gain" in js
    assert "basis_fact_ids" in js
    assert 'edge.relation === "reveals"' in js
    assert "adaptive_profile" in js
    assert "planning.revision" in js
    assert "execution_authority" in js


def test_execution_delta_trace_is_read_only():
    js = resources.files("tonmen.dashboard.static").joinpath("reports.js").read_text(encoding="utf-8")
    marker = 'view.className = "trace-execution-delta-view"'
    start = js.index(marker)
    execution_delta = js[start:]

    assert 'method:"POST"' not in execution_delta
    assert "/approve" not in execution_delta
    assert "/resume" not in execution_delta
    assert "/api/missions/start" not in execution_delta
    assert "read only" in execution_delta
