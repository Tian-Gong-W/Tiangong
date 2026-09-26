from __future__ import annotations

from typing import Any

from tonmen.missions import MissionPlan, MissionRun
from tonmen.policy import TargetScope

from .generator import build_report as _build_report
from .generator import render_markdown as _render_markdown


def _scope_from_plan(plan: MissionPlan) -> TargetScope | None:
    resolved = plan.metadata.get("resolved_assets") if isinstance(plan.metadata, dict) else None
    snapshot = resolved.get("scope_snapshot") if isinstance(resolved, dict) else None
    if not isinstance(snapshot, dict):
        return None
    allowed = tuple(str(item) for item in snapshot.get("allowed", []) if str(item))
    denied = tuple(str(item) for item in snapshot.get("denied", []) if str(item))
    return TargetScope(allowed=allowed, denied=denied)


def _asset_coverage(plan: MissionPlan, report: dict[str, Any]) -> dict[str, Any]:
    graph_nodes = report.get("graph", {}).get("nodes", [])
    planned_assets: dict[str, dict[str, Any]] = {}
    coverage_node: dict[str, Any] | None = None
    for node in graph_nodes:
        if not isinstance(node, dict):
            continue
        if node.get("kind") == "asset.resolved":
            metadata = node.get("metadata") if isinstance(node.get("metadata"), dict) else {}
            address = str(metadata.get("address") or node.get("label") or "").strip()
            if address:
                planned_assets[address] = dict(metadata)
        elif node.get("kind") == "coverage.plan":
            coverage_node = node.get("metadata") if isinstance(node.get("metadata"), dict) else {}

    correlation = report.get("asset_correlation") if isinstance(report.get("asset_correlation"), dict) else {}
    nmap = correlation.get("nmap") if isinstance(correlation.get("nmap"), dict) else {}
    scanned = list(dict.fromkeys(str(item) for item in nmap.get("scanned", []) if str(item)))
    observed_not_scanned = list(
        dict.fromkeys(str(item) for item in nmap.get("resolved_not_scanned", []) if str(item))
    )
    coverage = coverage_node or (
        plan.metadata.get("coverage_plan") if isinstance(plan.metadata, dict) else {}
    )
    direct_targets = set(str(item) for item in coverage.get("direct_nmap_targets", []) if str(item)) if isinstance(coverage, dict) else set()
    scope = _scope_from_plan(plan)

    addresses: list[str] = []
    for address in [*planned_assets.keys(), *scanned, *observed_not_scanned]:
        if address not in addresses:
            addresses.append(address)

    assets: list[dict[str, Any]] = []
    for address in addresses:
        metadata = planned_assets.get(address, {})
        authorized = bool(metadata.get("authorized"))
        if not metadata and scope is not None:
            try:
                authorized = scope.is_allowed(address)
            except ValueError:
                authorized = False
        scope_status = str(metadata.get("scope_status") or ("authorized" if authorized else "needs_scope"))
        was_scanned = address in scanned
        planned_direct = address in direct_targets
        assets.append(
            {
                "address": address,
                "family": str(metadata.get("family") or ("ipv6" if ":" in address else "ipv4")),
                "source": str(metadata.get("source") or ("nmap_dns" if address in observed_not_scanned else "nmap")),
                "authorized": authorized,
                "scope_status": scope_status,
                "planned_direct_nmap": planned_direct,
                "scanned": was_scanned,
                "observed_not_scanned": address in observed_not_scanned,
                "coverage_status": (
                    "scanned"
                    if was_scanned
                    else "planned"
                    if planned_direct
                    else "needs_scope"
                    if not authorized
                    else "authorized_uncovered"
                ),
            }
        )

    return {
        "host": coverage.get("primary_hostname") if isinstance(coverage, dict) else None,
        "web_target": coverage.get("web_target") if isinstance(coverage, dict) else plan.target,
        "web_backend_fanout": False,
        "assets": assets,
        "summary": {
            "resolved_assets": len(assets),
            "authorized_assets": sum(1 for item in assets if item["authorized"]),
            "needs_scope": sum(1 for item in assets if item["scope_status"] == "needs_scope"),
            "direct_nmap_planned": sum(1 for item in assets if item["planned_direct_nmap"]),
            "scanned_addresses": sum(1 for item in assets if item["scanned"]),
        },
        "note": (
            "DNS resolution is an asset observation, not an authorization grant. Direct IP coverage is generated only "
            "for IPs independently allowed by Scope. HTTPx/Nuclei keep the hostname so Host/SNI routing is preserved."
        ),
        "scope_action": "Add a concrete IP/CIDR to Scope and create a new plan before direct coverage of NEEDS_SCOPE assets.",
    }


def build_report(plan: MissionPlan, run: MissionRun) -> dict[str, Any]:
    report = _build_report(plan, run)
    report["asset_coverage"] = _asset_coverage(plan, report)
    report["time_semantics"] = {
        "canonical_timezone": "UTC",
        "raw_evidence_preserved": True,
        "raw_tool_timezone_may_differ": True,
        "console_display": "browser_local_with_utc_reference",
        "note": "TONMEN canonical timestamps are UTC. Raw tool output is preserved verbatim and may contain another timezone.",
    }
    return report


def render_markdown(report: dict[str, Any]) -> str:
    text = _render_markdown(report).rstrip() + "\n"
    coverage = report.get("asset_coverage") if isinstance(report.get("asset_coverage"), dict) else {}
    assets = coverage.get("assets", []) if isinstance(coverage, dict) else []
    lines = [
        "",
        "## Resolved Asset Coverage",
        "",
        str(coverage.get("note") or "No resolved-asset coverage metadata was recorded."),
        "",
        "| Address | Family | Scope | Direct Nmap planned | Scanned | Coverage |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for item in assets:
        if not isinstance(item, dict):
            continue
        lines.append(
            f"| `{item.get('address', '—')}` | {item.get('family', '—')} | {item.get('scope_status', '—')} | "
            f"{'yes' if item.get('planned_direct_nmap') else 'no'} | {'yes' if item.get('scanned') else 'no'} | "
            f"{item.get('coverage_status', '—')} |"
        )
    if not assets:
        lines.append("| — | — | — | no | no | no resolved assets |")
    lines.extend(
        [
            "",
            f"- Scope action: {coverage.get('scope_action') or '—'}",
            "",
            "## Time Semantics",
            "",
            "- Canonical TONMEN timestamps: **UTC**.",
            "- Raw Evidence is preserved verbatim; tool output may contain its own timezone (for example HKT).",
            "- Console presentation may render canonical timestamps in browser-local time while retaining the UTC reference.",
            "",
        ]
    )
    return text + "\n".join(lines)
