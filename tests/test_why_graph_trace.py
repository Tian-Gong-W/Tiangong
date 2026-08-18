from __future__ import annotations

from importlib import resources


def _why_graph_source() -> str:
    js = resources.files("tonmen.dashboard.static").joinpath("history-delete.js").read_text(encoding="utf-8")
    marker = "const WHY_GRAPH_PLUGIN = true;"
    return js[js.index(marker):]


def test_why_graph_traces_dynamic_tool_back_to_evidence_and_judgment():
    js = _why_graph_source()

    assert "Why Graph · 为什么选这个工具" in js
    assert "Evidence → Fact → Profile / Reasoner / Council → planning.revision → Dynamic Tool" in js
    assert "plan_revision_id" in js
    assert "basis_fact_ids" in js
    assert 'edge.relation === "reveals"' in js
    assert 'edge.relation === "supports_plan_revision"' in js
    assert 'edge.relation === "adds_step"' in js
    assert 'node.kind === "planning.revision"' in js
    assert 'node.kind !== "council.round"' in js
    assert "detail.reasoning" in js
    assert "expected_information_gain" in js
    assert "execution_authority" in js


def test_why_graph_can_be_opened_from_dynamic_execution_delta_step():
    js = _why_graph_source()

    assert "data-open-why-step" in js
    assert "data-why-select-step" in js
    assert 'button.textContent = "Why?"' in js
    assert "trace-execution-delta-view" in js
    assert "scrollIntoView" in js


def test_why_graph_is_read_only_and_does_not_create_execution_authority():
    js = _why_graph_source()

    assert 'method: "POST"' not in js
    assert 'method:"POST"' not in js
    assert "/api/missions/start" not in js
    assert "/approve" not in js
    assert "/resume" not in js
    assert "read only" in js
