from importlib import resources

from tonmen.dashboard import DashboardState, serve_dashboard
from tonmen.dashboard.simple_view_server import SimpleViewDashboardHandler
from tonmen.dashboard.usability_server import DashboardState as UsabilityDashboardState


def test_dashboard_keeps_existing_state_and_uses_simple_view_server():
    assert DashboardState is UsabilityDashboardState
    assert callable(serve_dashboard)
    assert issubclass(SimpleViewDashboardHandler, object)


def test_simple_module_assets_are_packaged():
    static = resources.files("tonmen.dashboard.static")
    js = static.joinpath("module-simple-view.js").read_text(encoding="utf-8")
    css = static.joinpath("module-simple-view.css").read_text(encoding="utf-8")

    assert "可以使用" in js
    assert "详细信息" in js
    assert "证据信息" in js
    assert "运行设置" in js
    assert "当前运行正常" in js
    assert "全部设置" in js
    assert ".module-simple-details" in css
    assert ".simple-settings-grid" in css


def test_tools_view_keeps_technical_fields_behind_details():
    js = resources.files("tonmen.dashboard.static").joinpath("module-simple-view.js").read_text(encoding="utf-8")
    assert 'detailsBlock("详细信息"' in js
    assert "类别" in js
    assert "检查" in js
    assert "simple-cap-list" in js


def test_intelligence_view_uses_plain_chinese_labels():
    js = resources.files("tonmen.dashboard.static").joinpath("module-simple-view.js").read_text(encoding="utf-8")
    for text in ("主机", "服务", "网站", "漏洞", "严重", "查看任务", "证据 ID"):
        assert text in js


def test_settings_view_shows_small_summary_and_folds_full_config():
    js = resources.files("tonmen.dashboard.static").joinpath("module-simple-view.js").read_text(encoding="utf-8")
    for text in ("运行目录", "控制台", "命令超时", "授权目标", "全部设置", "检查详情"):
        assert text in js
