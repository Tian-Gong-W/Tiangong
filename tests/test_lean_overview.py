from importlib import resources


def test_overview_is_utility_first_not_a_module_wall():
    static = resources.files("tonmen.dashboard.static")
    html = static.joinpath("index.html").read_text(encoding="utf-8")
    css = static.joinpath("viewport.css").read_text(encoding="utf-8")

    # Overview keeps only the operational essentials in the lean layout.
    for required in (
        'id="command-deck"',
        'id="scope-panel"',
        'id="chronicle-panel"',
        'id="approval-panel"',
    ):
        assert required in html

    # Detailed module walls are absent from the Overview markup.
    for removed in ('id="status-grid"', 'id="mission-panel"', 'id="intel-panel"', 'id="reason-panel"'):
        assert removed not in html

    # Idle approval is hidden until a human decision is actually required.
    assert "#overview #approval-panel:has(.approval-body.idle){display:none!important}" in css


def test_overview_removes_nonfunctional_decorative_controls():
    css = resources.files("tonmen.dashboard.static").joinpath("viewport.css").read_text(encoding="utf-8")

    # Do not imply functionality with fake notification/help/operator controls.
    assert ".brand-tagline,.header-icon,.operator-card,.sidebar-art,.sidebar-poem{display:none!important}" in css

    # The command deck should remain compact and flat.
    assert "#overview .command-deck{" in css
    assert "box-shadow:none!important" in css
