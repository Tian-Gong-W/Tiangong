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
    assert 'round.kind !== "council.round"' in js
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


def test_why_graph_external_styles_prevent_inline_csp_injection_path():
    static = resources.files("tonmen.dashboard.static")
    index = static.joinpath("index.html").read_text(encoding="utf-8")
    css = static.joinpath("history-delete.css").read_text(encoding="utf-8")
    js = _why_graph_source()

    # The external viewport stylesheet is predeclared with the sentinel ID checked
    # by ensureStyles(), so its inline <style> fallback is never executed under
    # Console CSP style-src 'self'.
    assert 'id="tonmen-why-graph-style"' in index
    assert 'href="/assets/viewport.css' in index
    assert '.why-graph-view' in css
    assert '.why-chain' in css
    assert "style-src 'self'" in css
    assert 'document.getElementById("tonmen-why-graph-style")' in js
