from __future__ import annotations

from importlib import resources


def test_module_route_refresh_is_single_flight_and_change_aware():
    source = resources.files("tonmen.dashboard.static").joinpath("module-pages.js").read_text(encoding="utf-8")

    assert "rendering: false" in source
    assert "renderPending: false" in source
    assert "if (pageState.rendering)" in source
    assert "pageState.renderPending = true" in source
    assert "pageState.rendering = false" in source
    assert "queueMicrotask(() => renderRoute(true))" in source
    assert "document.hidden || pageState.busy || pageState.rendering" in source

    # Polling may fetch fresh data, but identical view data must not replace the
    # module root DOM. Replacing the entire root every timer tick caused visible
    # flicker even when nothing had changed.
    assert "const signature = `${actions}\\u0000${body}`" in source
    assert "if (pageState.cache[route] === signature) return false" in source
    assert "pageState.cache[route] = signature" in source
    assert "if (changed) bindMissionSelection()" in source
    assert "}, 15000);" in source


def test_overview_periodic_refresh_is_single_flight_and_change_aware():
    source = resources.files("tonmen.dashboard.static").joinpath("app.js").read_text(encoding="utf-8")

    assert "refreshing: false" in source
    assert "polling: false" in source
    assert "if (state.refreshing) return" in source
    assert "if (document.hidden || state.polling) return" in source
    assert "state.polling = true" in source
    assert "state.polling = false" in source

    assert "currentViewSignature: null" in source
    assert "scopeViewSignature: null" in source
    assert "function missionViewSignature(m)" in source
    assert "function renderMissionIfChanged(loaded)" in source
    assert "if (state.currentViewSignature === signature) return false" in source
    assert "if (state.scopeViewSignature === signature) return" in source
    assert "}, 15000);" in source
