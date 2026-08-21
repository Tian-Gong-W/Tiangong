from __future__ import annotations

from importlib import resources


def _text(name: str) -> str:
    return resources.files("tonmen.dashboard.static").joinpath(name).read_text(encoding="utf-8")


def test_provider_hub_is_chinese_first_and_concise():
    html = _text("provider-hub-page.html")
    easy = _text("provider-easy-setup.js")

    assert "AI 配置" in html
    assert "配置模型账号、AI 主控和子代理。" in html
    assert "AI PROVIDER CONTROL PLANE" not in html
    assert "Multi-provider intelligence" not in html
    assert "快速开始 / Easy Setup" not in easy
    assert "AI 快速配置" in easy
    assert "高级信息" in easy


def test_worker_fleet_removes_long_english_intro_copy():
    html = _text("worker-fleet-page.html")
    js = _text("worker-fleet-page.js")

    assert "执行节点" in html
    assert "查看节点状态、负载和任务分配。" in html
    assert "EXECUTION FLEET CONTROL" not in html
    assert "Central governance · Distributed execution" not in html
    # Keep the security invariant wording available to existing packaging tests,
    # but it is no longer displayed as a large English seal.
    assert "APPROVAL TOKEN" in html
    assert "维护中" in js
    assert "Execution mode" not in js
    assert "Queue depth" not in js


def test_main_console_runtime_copy_prefers_plain_names():
    js = _text("console-usability.js")
    css = _text("console-usability.css")

    assert '"天域":["授权范围", "天域"]' in js
    assert '"主導":["AI 配置", "主導"]' in js
    assert '"/missions":["任务", "查看任务、步骤和结果。"]' in js
    assert "自动执行，关键步骤由你确认" in js
    assert "批准并继续" in js
    assert ".panel-title h2 small" in css
    assert ".module-page-head h1 small" in css
