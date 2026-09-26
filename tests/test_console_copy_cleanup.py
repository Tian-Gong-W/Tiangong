from importlib import resources


def test_main_console_translates_remaining_module_and_report_labels():
    static = resources.files("tonmen.dashboard.static")
    js = static.joinpath("console-usability.js").read_text(encoding="utf-8")

    for text in (
        '"Total":"总数"',
        '"Waiting approval":"等待批准"',
        '"Allowed Scope":"已授权"',
        '"Doctor / Runtime Readiness":"运行检查"',
        '"Finding Verification":"漏洞确认"',
        '"Raw Evidence":"原始证据"',
        '"治理 / Governance":"安全控制"',
        '"完整执行报告 / Mission Report":"任务报告"',
    ):
        assert text in js

    assert "模板命中、证据确认、漏洞归因分别判断。" in js
    assert "DNS 解析只用于观察，不会自动扩大授权范围。" in js


def test_report_keeps_conclusions_visible_and_folds_technical_sections():
    static = resources.files("tonmen.dashboard.static")
    js = static.joinpath("console-usability.js").read_text(encoding="utf-8")
    css = static.joinpath("console-usability.css").read_text(encoding="utf-8")

    assert 'advancedReportSections = new Set(["时间", "安全控制", "原始发现", "执行请求", "AI 评审", "判断记录", "原始证据"])' in js
    assert 'compactSummaryFields = new Set(["开始时间", "结束时间", "已合并重复", "评审轮次", "子代理评审"])' in js
    assert "report-advanced-section" in js
    assert ".report-advanced-section" in css
    assert ".simple-report-secondary" in css
    for primary in ("漏洞合并", "漏洞确认", "资产覆盖", "执行步骤"):
        assert primary not in js.split("advancedReportSections = new Set(", 1)[1].split(");", 1)[0]


def test_primary_ai_and_worker_pages_do_not_restore_long_english_intros():
    static = resources.files("tonmen.dashboard.static")
    provider_html = static.joinpath("provider-hub-page.html").read_text(encoding="utf-8")
    worker_html = static.joinpath("worker-fleet-page.html").read_text(encoding="utf-8")

    assert "AI 配置" in provider_html
    assert "配置模型账号、AI 主控和子代理。" in provider_html
    assert "AI PROVIDER CONTROL PLANE" not in provider_html
    assert "Multi-provider intelligence" not in provider_html

    assert "执行节点" in worker_html
    assert "主控授权" in worker_html
    assert "节点执行" in worker_html
    assert "回传证据" in worker_html
    assert "EXECUTION FLEET CONTROL" not in worker_html
    assert "Central governance · Distributed execution" not in worker_html
