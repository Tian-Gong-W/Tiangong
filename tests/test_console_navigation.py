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
        "/lead",
        "/loop",
        "/chronicle",
        "/approval",
        "/settings",
    }
    assert _APP_ROUTES == expected

    # The lean sidebar exposes primary workspaces as native links. Legacy module
    # routes stay server-addressable and are rendered by module-pages.js.
    primary_routes = {"/", "/missions", "/tools", "/lead", "/guard", "/settings"}
    for route in primary_routes:
        assert f'href="{route}"' in html

    assert '<a class="nav-item"' in html
    assert 'data-scroll=' not in html

    # Cache-busted assets make a freshly updated Console request the current UI bundle.
    assert '/assets/app.js?v=lean-nav-1' in html
    assert '/assets/viewport.css?v=lean-nav-1' in html


def test_module_page_assets_render_detailed_execution_workspaces():
    static = resources.files("tonmen.dashboard.static")
    module_script = static.joinpath("module-pages.js").read_text(encoding="utf-8")

    assert 'root.id = "module-page-root"' in module_script
    assert '"/missions": ["任务", "完整任务工作台"' in module_script
    assert '"/tools": ["工具", "已注册能力"' in module_script
    assert '"/lead": ["主导", "主导智能"' in module_script
    assert '"/approval": ["审批队列", "Approval"' in module_script
    assert '执行内容' in module_script
    assert 'stdout' in module_script
    assert 'stderr' in module_script
