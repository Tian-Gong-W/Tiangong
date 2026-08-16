from importlib import resources


def test_console_loads_viewport_resilience_styles():
    static = resources.files("tonmen.dashboard.static")
    html = static.joinpath("index.html").read_text(encoding="utf-8")
    css = static.joinpath("viewport.css").read_text(encoding="utf-8")

    assert 'href="/assets/viewport.css"' in html
    assert "overflow-y:auto" in css
    assert "max-height:calc(100dvh" in css
    assert "@media (max-height:850px)" in css
    assert ".dialog-actions{position:sticky" in css
