from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from tonmen.reports import build_report

_TOOL_TITLES = {
    "nmap": "网络探测",
    "httpx": "网站识别",
    "nuclei": "漏洞验证",
}


def _host_of(target: str) -> str:
    parsed = urlparse(target if "://" in target else f"//{target}")
    return (parsed.hostname or target).rstrip(".").lower()


def _state_of(execution) -> str:
    return execution.state.value if execution is not None else "pending"


def _node(id_: str, kind: str, title: str, **extra: object) -> dict[str, Any]:
    return {"id": id_, "kind": kind, "title": title, **extra}


def _edge(source: str, target: str, relation: str) -> dict[str, str]:
    return {"source": source, "target": target, "relation": relation}


def _build_exploration(plan, run, report: dict[str, Any]) -> dict[str, Any]:
    goal_id = f"goal:{plan.id}"
    nodes: list[dict[str, Any]] = [
        _node(goal_id, "goal", plan.target, detail="任务目标", state=run.state.value)
    ]
    edges: list[dict[str, str]] = []
    execution_by_step = {item.step_id: item for item in run.steps}

    evidence_to_step: dict[str, str] = {}
    for graph_edge in run.graph.edges:
        if graph_edge.relation == "produced":
            evidence_to_step[graph_edge.target] = graph_edge.source

    intent_ids: dict[str, str] = {}
    for index, step in enumerate(plan.steps, start=1):
        execution = execution_by_step.get(step.id)
        intent_id = f"intent:{step.id}"
        intent_ids[step.id] = intent_id
        title = _TOOL_TITLES.get(step.tool, step.tool)
        nodes.append(
            _node(
                intent_id,
                "intent",
                title,
                detail=step.rationale,
                target=step.target,
                tool=step.tool,
                order=index,
                state=_state_of(execution),
                risk=step.risk,
                requires_approval=step.requires_approval,
                evidence_id=getattr(execution, "evidence_id", None),
            )
        )
        edges.append(_edge(goal_id, intent_id, "计划"))

    fact_ids: dict[str, str] = {}
    for graph_node in run.graph.nodes.values():
        if not graph_node.kind.startswith("intelligence.") or graph_node.kind == "intelligence.finding":
            continue
        fact_id = f"fact:{graph_node.id}"
        fact_ids[graph_node.id] = fact_id
        metadata = dict(graph_node.metadata)
        data = metadata.get("data") if isinstance(metadata.get("data"), dict) else {}
        evidence_id = str(metadata.get("evidence_id") or "")
        step_id = evidence_to_step.get(evidence_id)
        nodes.append(
            _node(
                fact_id,
                "fact",
                graph_node.label,
                detail=str(data.get("detail") or data.get("url") or ""),
                fact_kind=graph_node.kind.removeprefix("intelligence."),
                target=metadata.get("target"),
                severity=metadata.get("severity"),
                confidence=metadata.get("confidence"),
                evidence_id=evidence_id or None,
            )
        )
        edges.append(_edge(intent_ids.get(step_id, goal_id), fact_id, "发现"))

    for graph_node in run.graph.nodes.values():
        if not graph_node.kind.startswith("reasoning."):
            continue
        metadata = dict(graph_node.metadata)
        decision_id = f"decision:{graph_node.id}"
        nodes.append(
            _node(
                decision_id,
                "decision",
                graph_node.label,
                detail=str(metadata.get("action") or "判断"),
                action=metadata.get("action"),
                requires_human=bool(metadata.get("requires_human")),
            )
        )
        basis = [str(item) for item in metadata.get("basis_fact_ids", []) if str(item)]
        linked = False
        for raw_fact_id in basis:
            source = fact_ids.get(raw_fact_id)
            if source:
                edges.append(_edge(source, decision_id, "依据"))
                linked = True
        if not linked:
            edges.append(_edge(goal_id, decision_id, "判断"))
        next_step = str(metadata.get("next_step_id") or "")
        if next_step and next_step in intent_ids:
            edges.append(_edge(decision_id, intent_ids[next_step], "建议"))

    finding_nodes = []
    for aggregate in report.get("aggregated_findings", []):
        finding_id = f"finding:{aggregate['id']}"
        finding_nodes.append(finding_id)
        nodes.append(
            _node(
                finding_id,
                "finding",
                str(aggregate.get("name") or aggregate.get("template_id") or "漏洞"),
                severity=aggregate.get("severity"),
                evidence_status=aggregate.get("evidence_status"),
                attribution_status=aggregate.get("attribution_status"),
                confidence=aggregate.get("confidence"),
                backends=[item.get("backend") for item in aggregate.get("affected_backends", []) if item.get("backend")],
            )
        )
        parent_intents: list[str] = []
        for evidence_id in aggregate.get("evidence_ids", []):
            step_id = evidence_to_step.get(str(evidence_id))
            intent_id = intent_ids.get(step_id or "")
            if intent_id and intent_id not in parent_intents:
                parent_intents.append(intent_id)
        if not parent_intents:
            parent_intents = [goal_id]
        for parent in parent_intents:
            edges.append(_edge(parent, finding_id, "确认"))

    return {
        "nodes": nodes,
        "edges": edges,
        "counts": {
            "intents": len(intent_ids),
            "facts": len(fact_ids),
            "decisions": sum(1 for item in nodes if item["kind"] == "decision"),
            "findings": len(finding_nodes),
        },
        "authority": {
            "execution": False,
            "approval": False,
            "scope": False,
            "plan_mutation": False,
        },
    }


def _build_assets(plan, run, report: dict[str, Any]) -> dict[str, Any]:
    metadata = dict(plan.metadata or {})
    resolved = dict(metadata.get("resolved_assets") or {})
    coverage = dict(metadata.get("coverage_plan") or {})
    host = str(resolved.get("host") or _host_of(plan.target))
    root_id = f"asset:host:{host}"
    nodes: dict[str, dict[str, Any]] = {
        root_id: _node(root_id, "host", host, scope_status="authorized", source="mission")
    }
    edges: list[dict[str, str]] = []
    address_to_id: dict[str, str] = {}

    nmap = report.get("asset_correlation", {}).get("nmap", {})
    scanned = {str(item) for item in nmap.get("scanned", [])}
    reported_not_scanned = {str(item) for item in nmap.get("resolved_not_scanned", [])}
    planned_direct = {str(item) for item in coverage.get("direct_nmap_targets", [])}

    for item in resolved.get("assets", []):
        if not isinstance(item, dict) or not item.get("address"):
            continue
        address = str(item["address"])
        asset_id = f"asset:ip:{address}"
        address_to_id[address] = asset_id
        if address in scanned:
            coverage_status = "scanned"
        elif address in planned_direct:
            coverage_status = "planned"
        elif item.get("authorized"):
            coverage_status = "authorized_uncovered"
        else:
            coverage_status = "needs_scope"
        nodes[asset_id] = _node(
            asset_id,
            "ip",
            address,
            family=item.get("family"),
            scope_status=item.get("scope_status"),
            authorized=bool(item.get("authorized")),
            coverage_status=coverage_status,
            source=item.get("source") or "dns",
        )
        edges.append(_edge(root_id, asset_id, "解析"))

    intelligence = [node for node in run.graph.nodes.values() if node.kind.startswith("intelligence.")]
    for graph_node in intelligence:
        md = dict(graph_node.metadata)
        data = md.get("data") if isinstance(md.get("data"), dict) else {}
        if graph_node.kind == "intelligence.service":
            backend = str(data.get("scanned_address") or "")
            parent = address_to_id.get(backend, root_id)
            port = data.get("port")
            protocol = str(data.get("protocol") or "tcp")
            service = str(data.get("service") or "service")
            asset_id = f"asset:service:{parent}:{port}:{protocol}"
            nodes[asset_id] = _node(
                asset_id,
                "service",
                f"{port}/{protocol} · {service}",
                port=port,
                protocol=protocol,
                service=service,
                detail=data.get("detail"),
                evidence_id=md.get("evidence_id"),
            )
            if not any(edge["source"] == parent and edge["target"] == asset_id for edge in edges):
                edges.append(_edge(parent, asset_id, "服务"))
        elif graph_node.kind == "intelligence.web":
            url = str(data.get("url") or md.get("target") or plan.target)
            asset_id = f"asset:web:{graph_node.id}"
            nodes[asset_id] = _node(
                asset_id,
                "web",
                url,
                status_code=data.get("status_code"),
                title=data.get("title"),
                technologies=list(data.get("technologies") or []),
                evidence_id=md.get("evidence_id"),
            )
            edges.append(_edge(root_id, asset_id, "网站"))

    finding_asset_ids: dict[str, list[str]] = {}
    for aggregate in report.get("aggregated_findings", []):
        finding_id = f"asset:finding:{aggregate['id']}"
        nodes[finding_id] = _node(
            finding_id,
            "finding",
            str(aggregate.get("name") or aggregate.get("template_id") or "漏洞"),
            severity=aggregate.get("severity"),
            evidence_status=aggregate.get("evidence_status"),
            attribution_status=aggregate.get("attribution_status"),
            confidence=aggregate.get("confidence"),
        )
        parents: list[str] = []
        for backend in aggregate.get("affected_backends", []):
            value = str(backend.get("backend") or "").strip()
            if not value or value == "unknown":
                continue
            parent = address_to_id.get(value)
            if parent is None:
                parent = f"asset:backend:{value}"
                if parent not in nodes:
                    nodes[parent] = _node(
                        parent,
                        "backend",
                        value,
                        scope_status="observed",
                        authorized=None,
                        coverage_status="observed",
                        source="validation",
                    )
                    edges.append(_edge(root_id, parent, "观察到"))
                address_to_id[value] = parent
            if parent not in parents:
                parents.append(parent)
        if not parents:
            parents = [root_id]
        finding_asset_ids[str(aggregate["id"])] = parents
        for parent in parents:
            edges.append(_edge(parent, finding_id, "影响"))

    # Nmap may explicitly report DNS answers it did not scan even when the plan's
    # passive resolver snapshot did not contain them. Preserve those as observations
    # without implying Scope or coverage.
    for address in sorted(reported_not_scanned):
        if address in address_to_id:
            continue
        asset_id = f"asset:backend:{address}"
        nodes[asset_id] = _node(
            asset_id,
            "backend",
            address,
            scope_status="observed",
            authorized=None,
            coverage_status="not_scanned",
            source="nmap",
        )
        address_to_id[address] = asset_id
        edges.append(_edge(root_id, asset_id, "观察到"))

    return {
        "root_id": root_id,
        "nodes": list(nodes.values()),
        "edges": edges,
        "finding_asset_ids": finding_asset_ids,
        "summary": {
            "assets": sum(1 for item in nodes.values() if item["kind"] != "finding"),
            "resolved_addresses": len(resolved.get("assets", [])),
            "scanned_addresses": len(scanned),
            "needs_scope": len(resolved.get("needs_scope", [])),
            "findings": len(report.get("aggregated_findings", [])),
        },
        "semantics": {
            "dns_resolution_expands_scope": False,
            "finding_affects_only_linked_assets": True,
            "observed_backend_is_not_scope_grant": True,
        },
    }


def build_mission_workspace(plan, run) -> dict[str, Any]:
    """Create a read-only task workspace projection from existing governed records.

    This projection never creates facts, grants Scope, changes the plan, or executes
    a tool. It only reorganizes Plan / Evidence / Intelligence / Reasoning / Finding
    records into operator-friendly exploration and asset views.
    """

    report = build_report(plan, run)
    assets = _build_assets(plan, run, report)
    findings = []
    for aggregate in report.get("aggregated_findings", []):
        item = dict(aggregate)
        item["affected_asset_ids"] = list(assets["finding_asset_ids"].get(str(aggregate["id"]), []))
        findings.append(item)

    return {
        "exploration": _build_exploration(plan, run, report),
        "assets": assets,
        "findings": findings,
        "report": {
            "type": report.get("report_type"),
            "summary": dict(report.get("summary") or {}),
        },
        "views": ["exploration", "findings", "assets", "report"],
        "authority": {
            "execution": False,
            "approval": False,
            "scope": False,
            "plan_mutation": False,
            "fact_creation": False,
        },
    }
