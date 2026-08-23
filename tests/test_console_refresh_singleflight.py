from __future__ import annotations

from importlib import resources


def test_module_route_refresh_is_single_flight():
    source = resources.files("tonmen.dashboard.static").joinpath("module-pages.js").read_text(encoding="utf-8")

    assert "rendering: false" in source
    assert "renderPending: false" in source
    assert "if (pageState.rendering)" in source
    assert "pageState.renderPending = true" in source
    assert "pageState.rendering = false" in source
    assert "queueMicrotask(() => renderRoute(true))" in source
    assert "document.hidden || pageState.busy || pageState.rendering" in source


def test_overview_periodic_refresh_is_single_flight():
    source = resources.files("tonmen.dashboard.static").joinpath("app.js").read_text(encoding="utf-8")

    assert "refreshing: false" in source
    assert "polling: false" in source
    assert "if (state.refreshing) return" in source
    assert "if (document.hidden || state.polling) return" in source
    assert "state.polling = true" in source
    assert "state.polling = false" in source
