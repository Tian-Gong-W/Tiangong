from __future__ import annotations

from importlib import resources


def test_console_exposes_evidence_confidence_conflict_view():
    js = resources.files("tonmen.dashboard.static").joinpath("artifacts.js").read_text(encoding="utf-8")
    css = resources.files("tonmen.dashboard.static").joinpath("artifacts.css").read_text(encoding="utf-8")

    assert "Evidence Confidence · 证据置信度 / 冲突" in js
    assert "SUPPORTED" in js
    assert "CONFLICTED" in js
    assert "UNRESOLVED" in js
    assert "absence of evidence ≠ contradictory evidence" in js
    assert "evidence_confidence" in js
    assert "conflict_fact_ids" in js
    assert "conflict_analyst" in js
    assert ".evidence-confidence-view" in css
    assert '[data-confidence="conflicted"]' in css


def test_evidence_confidence_console_plugin_is_read_only():
    js = resources.files("tonmen.dashboard.static").joinpath("artifacts.js").read_text(encoding="utf-8")
    marker = 'if (path !== "/missions") return;'
    confidence_plugin = js[js.rindex(marker):]

    assert 'method: "POST"' not in confidence_plugin
    assert 'method:"POST"' not in confidence_plugin
    assert "/api/missions/start" not in confidence_plugin
    assert "/approve" not in confidence_plugin
    assert "/resume" not in confidence_plugin
    assert "read only" in confidence_plugin
