from importlib import resources


def test_overview_is_utility_first_not_a_module_wall():
    static = resources.files("tonmen.dashboard.static")
    html = static.joinpath("index.html").read_text(encoding="utf-8")
    css = static.joinpath("viewport.css").read_text(encoding="utf-8")

    # Overview keeps the operational essentials.
    for required in (
        'id="status-grid"',
        'id="command-deck"',
        'id="mission-panel"',
        'id="chronicle-panel"',
        'id="approval-panel"',
    ):
        assert required in html

    # Detailed module content is not duplicated visually on the Overview.
    assert "#overview #intel-panel,#overview #reason-panel,#overview .graph-panel{display:none!important}" in css
    assert "#overview .scope-panel{display:none!important}" in css
    assert "#overview .loop-visual{display:none!important}" in css

    # Idle approval is hidden until a human decision is actually required.
    assert "#overview #approval-panel:has(.approval-body.idle){display:none!important}" in css


def test_overview_removes_nonfunctional_decorative_controls():
    css = resources.files("tonmen.dashboard.static").joinpath("viewport.css").read_text(encoding="utf-8")

    # Do not imply functionality with fake notification/help/operator controls.
    assert ".brand-tagline,.header-icon,.operator-card,.sidebar-art,.sidebar-poem{display:none!important}" in css

    # The summary strip and command deck should be compact and flat.
    assert "#overview .status-card{min-height:58px" in css
    assert "#overview .command-deck{" in css
    assert "box-shadow:none!important" in css
