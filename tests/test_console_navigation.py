from importlib import resources

from tonmen.dashboard.server import _APP_ROUTES


def test_sidebar_module_clicks_use_real_console_routes():
    script = resources.files("tonmen.dashboard.static").joinpath("deck.js").read_text(encoding="utf-8")

    expected = {
        "/",
        "/missions",
        "/scope",
        "/guard",
        "/tools",
        "/intelligence",
        "/reasoner",
        "/loop",
        "/chronicle",
        "/approval",
        "/settings",
    }
    assert _APP_ROUTES == expected
    for route in expected:
        assert f'"{route}"' in script

    # Capture-phase hard navigation must run before legacy Overview scroll handlers.
    assert 'document.addEventListener("click"' in script
    assert 'location.assign(route)' in script
    assert 'event.stopImmediatePropagation()' in script
    assert '}, true);' in script


def test_module_page_assets_are_part_of_the_app_bundle_contract():
    static = resources.files("tonmen.dashboard.static")
    module_script = static.joinpath("module-pages.js").read_text(encoding="utf-8")

    # A routed URL must render a detailed workspace rather than another Overview card.
    assert 'root.id = "module-page-root"' in module_script
    assert '"/missions": ["任務", "Missions"' in module_script
    assert '"/tools": ["天工", "Tools"' in module_script
    assert '"/approval": ["審批", "Approval"' in module_script
    assert 'Execution Content' in module_script
    assert 'stdout' in module_script
    assert 'stderr' in module_script
