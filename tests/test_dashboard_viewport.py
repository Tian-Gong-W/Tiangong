from importlib import resources

from tonmen.dashboard.server import _STATIC_TYPES


def test_console_loads_viewport_resilience_styles():
    static = resources.files("tonmen.dashboard.static")
    html = static.joinpath("index.html").read_text(encoding="utf-8")
    css = static.joinpath("viewport.css").read_text(encoding="utf-8")

    assert 'href="/assets/viewport.css"' in html
    assert "overflow-y:auto" in css
    assert "max-height:calc(100dvh" in css
    assert "@media (max-height:850px)" in css
    assert ".dialog-actions{position:sticky" in css
    assert "command-deck" in css


def test_main_panel_centralizes_common_governed_actions():
    static = resources.files("tonmen.dashboard.static")
    html = static.joinpath("index.html").read_text(encoding="utf-8")
    deck = static.joinpath("deck.js").read_text(encoding="utf-8")

    for control_id in (
        "deck-new-mission",
        "deck-refresh",
        "deck-resume",
        "deck-approve",
        "deck-evidence",
        "deck-retry",
        "deck-scope-form",
    ):
        assert f'id="{control_id}"' in html

    assert 'clickProxy("#approve-btn"' in deck
    assert 'clickProxy("#resume-btn"' in deck
    assert 'clickProxy("#evidence-btn"' in deck
    assert 'clickProxy("#retry-btn"' in deck
    assert 'sourceForm.dispatchEvent(new Event("submit"' in deck


def test_dashboard_server_serves_new_static_assets():
    assert _STATIC_TYPES["viewport.css"].startswith("text/css")
    assert _STATIC_TYPES["deck.js"].startswith("text/javascript")
