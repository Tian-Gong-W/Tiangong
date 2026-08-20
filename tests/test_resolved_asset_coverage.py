from __future__ import annotations

from tonmen.agents import MissionPlanner
from tonmen.assets import build_resolved_asset_set
from tonmen.chronicle import ChronicleStore
from tonmen.core.config import TonmenConfig
from tonmen.core.runtime import TonmenRuntime
from tonmen.missions import MissionRun
from tonmen.policy import TargetScope
from tonmen.reports import build_report, render_markdown


def _asset_set(target, scope):
    return build_resolved_asset_set(
        target,
        scope,
        resolver=lambda host: ["203.0.113.10", "198.51.100.20", "2001:db8::10"],
    )


def _runtime(tmp_path):
    return TonmenRuntime.sentinel(
        TonmenConfig(
            workspace=tmp_path,
            allowed_targets=("example.test", "203.0.113.0/24"),
        )
    )


def test_resolved_asset_set_separates_dns_observation_from_scope():
    scope = TargetScope(("example.test", "203.0.113.0/24"))

    result = _asset_set("https://example.test", scope)

    assert result["authorized_addresses"] == ["203.0.113.10"]
    assert result["needs_scope"] == ["198.51.100.20", "2001:db8::10"]
    assert result["semantics"]["dns_resolution_expands_scope"] is False
    assert result["semantics"]["direct_ip_execution_requires_ip_scope"] is True


def test_planner_observes_assets_but_does_not_fan_out_by_default(tmp_path, monkeypatch):
    monkeypatch.delenv("TONMEN_RESOLVED_IP_COVERAGE", raising=False)
    runtime = _runtime(tmp_path)
    plan = MissionPlanner(runtime, asset_resolver=_asset_set).plan("https://example.test")

    assert [step.tool for step in plan.steps] == ["nmap", "httpx", "nuclei"]
    assert [step.target for step in plan.steps] == ["example.test", "https://example.test", "https://example.test"]
    coverage = plan.metadata["coverage_plan"]
    assert coverage["resolved_ip_coverage_enabled"] is False
    assert coverage["eligible_direct_nmap_targets"] == ["203.0.113.10"]
    assert coverage["direct_nmap_targets"] == []
    assert coverage["needs_scope"] == ["198.51.100.20", "2001:db8::10"]


def test_planner_fans_out_only_to_independently_authorized_ips_when_enabled(tmp_path, monkeypatch):
    monkeypatch.setenv("TONMEN_RESOLVED_IP_COVERAGE", "1")
    runtime = _runtime(tmp_path)
    plan = MissionPlanner(runtime, asset_resolver=_asset_set).plan("https://example.test")

    nmap_targets = [step.target for step in plan.steps if step.tool == "nmap"]
    assert nmap_targets == ["example.test", "203.0.113.10"]
    assert "198.51.100.20" not in [step.target for step in plan.steps]
    assert "2001:db8::10" not in [step.target for step in plan.steps]
    assert [step.target for step in plan.steps if step.tool in {"httpx", "nuclei"}] == [
        "https://example.test",
        "https://example.test",
    ]


def test_resolved_assets_and_coverage_are_graph_provenance(tmp_path, monkeypatch):
    monkeypatch.setenv("TONMEN_RESOLVED_IP_COVERAGE", "1")
    runtime = _runtime(tmp_path)
    plan = MissionPlanner(runtime, asset_resolver=_asset_set).plan("https://example.test")
    run = MissionRun.create(plan)

    assets = [node for node in run.graph.nodes.values() if node.kind == "asset.resolved"]
    coverage = [node for node in run.graph.nodes.values() if node.kind == "coverage.plan"]
    assert len(assets) == 3
    assert len(coverage) == 1
    assert any(node.metadata["address"] == "203.0.113.10" and node.metadata["authorized"] for node in assets)
    assert any(node.metadata["address"] == "198.51.100.20" and not node.metadata["authorized"] for node in assets)
    assert all(node.metadata["execution_authority"] is False for node in assets)


def test_chronicle_round_trip_preserves_asset_plan_metadata(tmp_path, monkeypatch):
    monkeypatch.setenv("TONMEN_RESOLVED_IP_COVERAGE", "1")
    runtime = _runtime(tmp_path)
    plan = MissionPlanner(runtime, asset_resolver=_asset_set).plan("https://example.test")
    run = MissionRun.create(plan)
    store = ChronicleStore(tmp_path)

    store.save(plan, run)
    loaded_plan, loaded_run = store.load(run.id)

    assert loaded_plan.metadata["resolved_assets"]["needs_scope"] == ["198.51.100.20", "2001:db8::10"]
    assert loaded_plan.metadata["coverage_plan"]["direct_nmap_targets"] == ["203.0.113.10"]
    assert any(node.kind == "asset.resolved" for node in loaded_run.graph.nodes.values())


def test_report_exposes_asset_coverage_and_explicit_time_semantics(tmp_path, monkeypatch):
    monkeypatch.setenv("TONMEN_RESOLVED_IP_COVERAGE", "1")
    runtime = _runtime(tmp_path)
    plan = MissionPlanner(runtime, asset_resolver=_asset_set).plan("https://example.test")
    run = MissionRun.create(plan)

    report = build_report(plan, run)
    coverage = report["asset_coverage"]
    markdown = render_markdown(report)

    assert coverage["summary"]["resolved_assets"] == 3
    assert coverage["summary"]["needs_scope"] == 2
    authorized = next(item for item in coverage["assets"] if item["address"] == "203.0.113.10")
    assert authorized["scope_status"] == "authorized"
    assert authorized["planned_direct_nmap"] is True
    assert report["time_semantics"]["canonical_timezone"] == "UTC"
    assert "## Resolved Asset Coverage" in markdown
    assert "## Time Semantics" in markdown
    assert "NEEDS_SCOPE" not in markdown or "needs_scope" in markdown
