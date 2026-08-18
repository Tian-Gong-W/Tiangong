from importlib import resources


def test_missions_workbench_keeps_practical_legacy_interactions():
    static = resources.files("tonmen.dashboard.static")
    script = static.joinpath("events.js").read_text(encoding="utf-8")
    css = static.joinpath("events.css").read_text(encoding="utf-8")

    # Master/detail workbench with a draggable split, not two decorative cards.
    assert 'grid.classList.add("mission-workbench")' in script
    assert 'splitter.className = "mission-splitter"' in script
    assert 'localStorage.setItem("tonmen.missions.historySize"' in script
    assert ".mission-workbench{display:grid!important" in css
    assert "cursor:row-resize" in css

    # Fast history navigation: text search + state filter.
    assert 'id="mission-history-filter"' in script
    assert 'id="mission-state-filter"' in script
    assert 'sessionStorage.setItem("tonmen.missions.search"' in script
    assert 'sessionStorage.setItem("tonmen.missions.status"' in script

    # Detail data is split into useful tabs instead of one long raw-output wall.
    for tab in ("overview", "steps", "live", "stdout", "stderr", "evidence", "reasoning"):
        assert f'["{tab}",' in script or f'{tab}:' in script
    assert 'data-mission-tab="${key}"' in script
    assert ".mission-detail-tabs" in css
    assert ".mission-tab-panel.active" in css


def test_missions_workbench_preserves_raw_evidence_but_cleans_readable_output():
    script = resources.files("tonmen.dashboard.static").joinpath("events.js").read_text(encoding="utf-8")

    # Human-readable stdout/stderr strips ANSI escapes, while raw Evidence copy uses stored values.
    assert "const stripAnsi" in script
    assert 'copyButton("复制原始 stdout", item.stdout || "")' in script
    assert 'copyButton("复制原始 stderr", item.stderr || "")' in script
    assert 'navigator.clipboard.writeText' in script


def test_missions_workbench_cross_module_navigation_stays_governed():
    script = resources.files("tonmen.dashboard.static").joinpath("events.js").read_text(encoding="utf-8")

    # Cross-module actions carry only run context. They do not add a direct execution endpoint.
    for route in ("/intelligence?run=", "/reasoner?run=", "/chronicle?run=", "/approval?run="):
        assert route in script
    assert "/api/missions/start" not in script
    assert "/api/missions/" in script  # read-only detail fetch for the selected run


def test_missions_workbench_has_keyboard_efficiency_without_replacing_native_navigation():
    script = resources.files("tonmen.dashboard.static").joinpath("events.js").read_text(encoding="utf-8")

    assert 'event.key.toLowerCase() === "k"' in script
    assert 'document.getElementById("mission-history-filter")?.focus()' in script
    assert 'event.altKey && /^[1-7]$/.test(event.key)' in script


def test_missions_workbench_exposes_evidence_backed_decision_trace():
    static = resources.files("tonmen.dashboard.static")
    script = static.joinpath("history-delete.js").read_text(encoding="utf-8")
    css = static.joinpath("history-delete.css").read_text(encoding="utf-8")

    assert "Decision Trace · 决策轨迹" in script
    assert 'node.kind === "planning.revision"' in script
    assert 'node.kind.startsWith("reasoning.")' in script
    assert 'node.kind === "council.round"' in script
    assert '"contains_subagent"' in script
    assert 'node.kind === "loop.stop"' in script
    assert 'node.kind === "governance.report_gate"' in script
    assert "basis_fact_ids" in script
    assert "expected_information_gain" in script
    assert "execution_authority" in script
    assert ".decision-trace-timeline" in css
    assert ".trace-agent-grid" in css

    # Trace is read-only: it fetches the selected mission but does not start/approve/resume execution.
    assert 'fetch(`/api/missions/${encodeURIComponent(runId)}`' in script
    assert "/api/missions/start" not in script
    assert "/approve" not in script
    assert "/resume" not in script
