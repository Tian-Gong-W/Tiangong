from importlib import resources


def test_overview_next_action_links_directly_to_selected_decision_trace():
    script = resources.files("tonmen.dashboard.static").joinpath("deck.js").read_text(encoding="utf-8")

    assert "查看 Decision Trace / Delta →" in script
    assert "data-open-decision-trace" in script
    assert 'sessionStorage.setItem("tonmen.trace.activeRun", runId)' in script
    assert 'link.href = `/missions?run=${encodeURIComponent(runId)}`' in script
    assert "currentRunId" in script

    # Shortcut only selects the existing read-only trace. It does not add execution APIs.
    tail = script[script.index("查看 Decision Trace / Delta →"):]
    assert "/api/missions/start" not in tail
    assert "/approve" not in tail
    assert "/resume" not in tail
