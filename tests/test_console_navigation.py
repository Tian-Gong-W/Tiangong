from importlib import resources

from tonmen.dashboard.server import _APP_ROUTES


def test_sidebar_uses_native_links_for_core_console_workspaces():
    static = resources.files("tonmen.dashboard.static")
    html = static.joinpath("index.html").read_text(encoding="utf-8")
    artifacts_js = static.joinpath("artifacts.js").read_text(encoding="utf-8")

    core = {
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
    assert _APP_ROUTES == core | {"/artifacts"}

    # Core navigation remains available without JavaScript interception.
    for route in core:
        assert f'href="{route}"' in html

    # Binary Intelligence is added to the simplified operator navigation bundle.
    assert 'link.href = "/artifacts"' in artifacts_js
    assert "逆向 / Binary" in artifacts_js

    assert '<a class="nav-item"' in html
    assert 'data-scroll=' not in html

    # Cache-busted assets make a freshly updated Console request the current UI bundle.
    assert '/assets/app.js?v=native-nav-1' in html
    assert '/assets/viewport.css?v=native-nav-1' in html


def test_module_page_assets_render_detailed_execution_workspaces():
    static = resources.files("tonmen.dashboard.static")
    module_script = static.joinpath("module-pages.js").read_text(encoding="utf-8")
    artifact_script = static.joinpath("artifacts.js").read_text(encoding="utf-8")

    assert 'root.id = "module-page-root"' in module_script
    assert '"/missions": ["任務", "Missions"' in module_script
    assert '"/tools": ["天工", "Tools"' in module_script
    assert '"/approval": ["審批", "Approval"' in module_script
    assert 'Execution Content' in module_script
    assert 'stdout' in module_script
    assert 'stderr' in module_script

    assert 'root.id = "artifact-workbench"' in artifact_script
    assert "Artifact 静态分析" in artifact_script
    assert "execution_performed=false" in artifact_script
