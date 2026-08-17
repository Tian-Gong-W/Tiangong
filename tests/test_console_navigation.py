from importlib import resources

from tonmen.dashboard.server import _APP_ROUTES


def test_sidebar_uses_native_links_for_every_console_workspace():
    static = resources.files("tonmen.dashboard.static")
    html = static.joinpath("index.html").read_text(encoding="utf-8")

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

    # Navigation must work without JavaScript interception or manual URL entry.
    for route in expected:
        assert f'href="{route}"' in html

    assert '<a class="nav-item"' in html
    assert 'data-scroll=' not in html

    # Cache-busted assets make a freshly updated Console request the current UI bundle.
    assert '/assets/app.js?v=native-nav-1' in html
    assert '/assets/viewport.css?v=native-nav-1' in html


def test_module_page_assets_render_detailed_execution_workspaces():
    static = resources.files("tonmen.dashboard.static")
    module_script = static.joinpath("module-pages.js").read_text(encoding="utf-8")

    assert 'root.id = "module-page-root"' in module_script
    assert '"/missions": ["任務", "Missions"' in module_script
    assert '"/tools": ["天工", "Tools"' in module_script
    assert '"/approval": ["審批", "Approval"' in module_script
    assert 'Execution Content' in module_script
    assert 'stdout' in module_script
    assert 'stderr' in module_script
