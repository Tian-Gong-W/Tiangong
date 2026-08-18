from __future__ import annotations

import json
from datetime import timezone
from typing import Any

from tonmen.missions import MissionPlan, MissionRun


def _iso(value):
    return value.astimezone(timezone.utc).isoformat() if value else None


def _node(node) -> dict[str, Any]:
    return {"id": node.id, "kind": node.kind, "label": node.label, "metadata": dict(node.metadata)}


def _nuclei_payloads(evidence) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    if evidence.tool.strip().lower() != "nuclei":
        return items
    for line in evidence.stdout.splitlines():
        value = line.strip()
        if not value:
            continue
        try:
            data = json.loads(value)
        except json.JSONDecodeError:
            continue
        if not isinstance(data, dict):
            continue
        info = data.get("info") if isinstance(data.get("info"), dict) else {}
        items.append(
            {
                "template_id": data.get("template-id") or data.get("templateID"),
                "template": data.get("template"),
                "template_url": data.get("template-url"),
                "template_path": data.get("template-path"),
                "name": info.get("name"),
                "severity": info.get("severity"),
                "description": info.get("description"),
                "impact": info.get("impact"),
                "remediation": info.get("remediation"),
                "reference": info.get("reference"),
                "classification": info.get("classification"),
                "matched_at": data.get("matched-at") or data.get("matched"),
                "host": data.get("host"),
                "ip": data.get("ip"),
                "port": data.get("port"),
                "scheme": data.get("scheme"),
                "url": data.get("url"),
                "matcher_status": data.get("matcher-status"),
                "matcher_name": data.get("matcher-name") or data.get("matcher_name"),
                "request": data.get("request"),
                "response": data.get("response"),
                "timestamp": data.get("timestamp"),
                "evidence_id": evidence.id,
            }
        )
    return items


def _council(run: MissionRun) -> list[dict[str, Any]]:
    rounds = sorted(
        (node for node in run.graph.nodes.values() if node.kind == "council.round"),
        key=lambda node: int(node.metadata.get("round", 0)),
    )
    result: list[dict[str, Any]] = []
    for round_node in rounds:
        agents = []
        for edge in run.graph.edges:
            if edge.source != round_node.id or edge.relation != "contains_subagent":
                continue
            agent = run.graph.nodes.get(edge.target)
            if agent is not None:
                agents.append(_node(agent))
        result.append({**_node(round_node), "subagents": agents})
    return result


def _loop_policy(run: MissionRun) -> dict[str, Any]:
    sessions = [node for node in run.graph.nodes.values() if node.kind == "loop.session"]
    if not sessions:
        return {"assessment_rounds": 8, "subagents_per_round": 4}
    latest = sessions[-1]
    return dict(latest.metadata)


def _overlaps(left: list[str] | tuple[str, ...], right: list[str] | tuple[str, ...]) -> bool:
    return bool(set(left) & set(right))


def _adaptive_causality(plan: MissionPlan, run: MissionRun) -> list[dict[str, Any]]:
    """Build portable Why-Graph records from persisted provenance only.

    This function never executes tools or invents causal links. It follows the graph
    relations written by AdaptiveMissionPlanner and MissionCoordinator, then attaches
    Reasoner/Council context only when their recorded fact basis intersects the same
    planning-revision basis.
    """
    planned = {step.id: step for step in plan.steps}
    nodes = run.graph.nodes
    evidence_by_id = {item.id: item for item in run.evidence}
    reasoning_nodes = [node for node in nodes.values() if node.kind.startswith("reasoning.")]
    round_nodes = [node for node in nodes.values() if node.kind == "council.round"]
    result: list[dict[str, Any]] = []

    for execution in run.steps:
        revision_id = str(execution.metadata.get("plan_revision_id") or "")
        if not revision_id:
            continue
        revision = nodes.get(revision_id)
        if revision is None or revision.kind != "planning.revision":
            continue

        revision_md = dict(revision.metadata)
        basis_ids = [str(item) for item in revision_md.get("basis_fact_ids", [])]
        basis_set = set(basis_ids)
        facts = [_node(nodes[fact_id]) for fact_id in basis_ids if fact_id in nodes]

        evidence_ids: list[str] = []
        support_edges = 0
        adds_step = False
        for edge in run.graph.edges:
            if edge.relation == "reveals" and edge.target in basis_set and edge.source not in evidence_ids:
                evidence_ids.append(edge.source)
            if edge.relation == "supports_plan_revision" and edge.target == revision_id and edge.source in basis_set:
                support_edges += 1
            if edge.relation == "adds_step" and edge.source == revision_id and edge.target == execution.step_id:
                adds_step = True

        evidence_refs = []
        for evidence_id in evidence_ids:
            item = evidence_by_id.get(evidence_id)
            if item is None:
                continue
            evidence_refs.append(
                {
                    "id": item.id,
                    "tool": item.tool,
                    "target": item.target,
                    "argv": list(item.argv),
                    "exit_code": item.exit_code,
                }
            )

        reasoning = []
        reasoning_ids: set[str] = set()
        for node in reasoning_nodes:
            metadata = node.metadata
            node_basis = [str(item) for item in metadata.get("basis_fact_ids", [])]
            if metadata.get("next_step_id") == execution.step_id or _overlaps(basis_ids, node_basis):
                reasoning.append(_node(node))
                reasoning_ids.add(node.id)

        council = []
        for round_node in round_nodes:
            include = str(round_node.metadata.get("decision_id") or "") in reasoning_ids
            agents = []
            for edge in run.graph.edges:
                if edge.source != round_node.id or edge.relation != "contains_subagent":
                    continue
                agent = nodes.get(edge.target)
                if agent is None:
                    continue
                agent_fact_ids = [str(item) for item in agent.metadata.get("fact_ids", [])]
                if _overlaps(basis_ids, agent_fact_ids):
                    include = True
                agents.append(_node(agent))
            if include:
                council.append({**_node(round_node), "subagents": agents})

        step = planned.get(execution.step_id)
        result.append(
            {
                "step_id": execution.step_id,
                "tool": execution.tool,
                "target": execution.target,
                "risk": step.risk if step else None,
                "requires_approval": step.requires_approval if step else False,
                "state": execution.state.value,
                "revision": _node(revision),
                "basis_fact_ids": basis_ids,
                "basis_facts": facts,
                "evidence": evidence_refs,
                "profile": dict(execution.metadata.get("adaptive_profile", {})),
                "reasoning": reasoning,
                "council": council,
                "support_edges": support_edges,
                "adds_step_edge": adds_step,
                "expected_information_gain": revision_md.get("expected_information_gain"),
                "execution_authority": revision_md.get("execution_authority", False),
            }
        )

    return result


def build_report(plan: MissionPlan, run: MissionRun) -> dict[str, Any]:
    evidence = []
    payloads: list[dict[str, Any]] = []
    for item in run.evidence:
        payloads.extend(_nuclei_payloads(item))
        evidence.append(
            {
                "id": item.id,
                "tool": item.tool,
                "target": item.target,
                "argv": list(item.argv),
                "exit_code": item.exit_code,
                "stdout": item.stdout,
                "stderr": item.stderr,
                "started_at": _iso(item.started_at),
                "finished_at": _iso(item.finished_at),
            }
        )

    planned = {step.id: step for step in plan.steps}
    steps = []
    for execution in run.steps:
        step = planned.get(execution.step_id)
        steps.append(
            {
                "id": execution.step_id,
                "tool": execution.tool,
                "target": execution.target,
                "state": execution.state.value,
                "risk": step.risk if step else None,
                "requires_approval": step.requires_approval if step else False,
                "rationale": step.rationale if step else "",
                "parameters": dict(step.parameters) if step else {},
                "job_id": execution.job_id,
                "evidence_id": execution.evidence_id,
                "observation_id": execution.observation_id,
                "error": execution.error,
                "metadata": dict(execution.metadata),
            }
        )

    intelligence = [_node(node) for node in run.graph.nodes.values() if node.kind.startswith("intelligence.")]
    reasoning = [_node(node) for node in run.graph.nodes.values() if node.kind.startswith("reasoning.")]
    loop = [_node(node) for node in run.graph.nodes.values() if node.kind.startswith("loop.")]
    council = _council(run)
    causality = _adaptive_causality(plan, run)
    findings = [node for node in intelligence if node["kind"] == "intelligence.finding"]
    approval_steps = [step for step in steps if step["requires_approval"]]
    failures = [step for step in steps if step["state"] in {"failed", "denied"}]
    degraded = [step for step in steps if step["state"] == "degraded"]

    return {
        "schema": 1,
        "report_type": "final" if run.state.value in {"succeeded", "failed", "denied"} else "interim",
        "mission": {
            "run_id": run.id,
            "plan_id": plan.id,
            "target": run.target,
            "state": run.state.value,
            "started_at": _iso(run.started_at),
            "finished_at": _iso(run.finished_at),
        },
        "summary": {
            "steps": len(steps),
            "evidence_records": len(evidence),
            "intelligence_facts": len(intelligence),
            "findings": len(findings),
            "approval_gated_steps": len(approval_steps),
            "failed_or_denied_steps": len(failures),
            "degraded_steps": len(degraded),
            "executed_payloads": len(payloads),
            "assessment_rounds": len(council),
            "subagent_reviews": sum(len(item["subagents"]) for item in council),
            "adaptive_revisions": len(causality),
        },
        "governance": {
            "execution_model": "Scope -> Guard -> Approval -> structured adapter -> shell=False Executor",
            "approval_tokens_persisted": False,
            "arbitrary_shell": False,
            "policy": _loop_policy(run),
            "approval_steps": approval_steps,
        },
        "steps": steps,
        "observations": [
            {
                "id": item.id,
                "source": item.source,
                "target": item.target,
                "summary": item.summary,
                "evidence_id": item.evidence_id,
                "captured_at": _iso(item.captured_at),
                "metadata": dict(item.metadata),
            }
            for item in run.observations
        ],
        "intelligence": intelligence,
        "findings": findings,
        "reasoning": reasoning,
        "loop": loop,
        "assessment_council": council,
        "adaptive_causality": causality,
        "executed_payloads": payloads,
        "evidence": evidence,
        "graph": {
            "nodes": [_node(node) for node in run.graph.nodes.values()],
            "edges": [
                {"source": edge.source, "relation": edge.relation, "target": edge.target}
                for edge in run.graph.edges
            ],
        },
    }


def _fenced(text: Any, language: str = "text") -> str:
    value = "" if text is None else str(text)
    return f"```{language}\n{value}\n```"


def render_markdown(report: dict[str, Any]) -> str:
    mission = report["mission"]
    summary = report["summary"]
    lines = [
        f"# TONMEN Mission Report — {mission['target']}",
        "",
        f"- Report: **{report['report_type']}**",
        f"- Run: `{mission['run_id']}`",
        f"- State: **{mission['state']}**",
        f"- Started: `{mission['started_at']}`",
        f"- Finished: `{mission['finished_at']}`",
        "",
        "## Executive Summary",
        "",
        f"- Steps: {summary['steps']}",
        f"- Evidence records: {summary['evidence_records']}",
        f"- Intelligence facts: {summary['intelligence_facts']}",
        f"- Findings: {summary['findings']}",
        f"- Executed request/payload records: {summary['executed_payloads']}",
        f"- Assessment rounds: {summary['assessment_rounds']}",
        f"- Subagent reviews: {summary['subagent_reviews']}",
        f"- Adaptive plan revisions: {summary.get('adaptive_revisions', 0)}",
        "",
        "## Governance",
        "",
        f"- Execution model: {report['governance']['execution_model']}",
        "- Approval tokens persisted: no",
        "- Arbitrary shell: disabled",
        "",
        "## Execution Steps",
        "",
    ]
    for index, step in enumerate(report["steps"], start=1):
        lines.extend(
            [
                f"### {index}. {step['tool']} — {step['state']}",
                "",
                f"- Target: `{step['target']}`",
                f"- Risk: L{step['risk']}",
                f"- Approval required: {step['requires_approval']}",
                f"- Rationale: {step['rationale']}",
                f"- Error: {step['error'] or '—'}",
                f"- Evidence: `{step['evidence_id'] or '—'}`",
                "",
            ]
        )

    lines.extend(["## Adaptive Causality / Why Graph", ""])
    if report.get("adaptive_causality"):
        for index, chain in enumerate(report["adaptive_causality"], start=1):
            revision = chain.get("revision", {})
            md = revision.get("metadata", {})
            fact_labels = [item.get("label", item.get("id", "")) for item in chain.get("basis_facts", [])]
            evidence_ids = [item.get("id", "") for item in chain.get("evidence", [])]
            reasoning_actions = [item.get("metadata", {}).get("action", item.get("kind", "")) for item in chain.get("reasoning", [])]
            council_rounds = [item.get("metadata", {}).get("round") for item in chain.get("council", [])]
            lines.extend(
                [
                    f"### Why {index}: {chain.get('tool')} — dynamic plan revision",
                    "",
                    f"- Step: `{chain.get('step_id')}`",
                    f"- Revision: `{revision.get('id', '—')}`",
                    f"- Rationale: {md.get('rationale') or revision.get('label', '—')}",
                    f"- Expected information gain: {chain.get('expected_information_gain') or '—'}",
                    f"- Evidence: `{', '.join(evidence_ids) or '—'}`",
                    f"- Basis facts: {', '.join(fact_labels) or '—'}",
                    f"- Reasoner context: `{', '.join(str(item) for item in reasoning_actions) or '—'}`",
                    f"- Council rounds: `{', '.join(str(item) for item in council_rounds) or '—'}`",
                    f"- Support edges: `{chain.get('support_edges', 0)}`",
                    f"- Revision adds step edge: `{chain.get('adds_step_edge', False)}`",
                    f"- Execution authority: `{chain.get('execution_authority', False)}`",
                    f"- Profile: `{json.dumps(chain.get('profile', {}), ensure_ascii=False)}`",
                    "",
                ]
            )
    else:
        lines.extend(["No evidence-driven dynamic capability revisions were recorded.", ""])

    lines.extend(["## Evidence-backed Findings", ""])
    if report["findings"]:
        for finding in report["findings"]:
            md = finding.get("metadata", {})
            lines.extend(
                [
                    f"### {finding['label']}",
                    "",
                    f"- Severity: **{md.get('severity', 'unknown')}**",
                    f"- Target: `{md.get('target', mission['target'])}`",
                    f"- Evidence: `{md.get('evidence_id', '—')}`",
                    f"- Data: `{json.dumps(md.get('data', {}), ensure_ascii=False)}`",
                    "",
                ]
            )
    else:
        lines.extend(["No evidence-backed finding facts were produced.", ""])

    lines.extend(["## Executed Requests / Payloads", ""])
    if report["executed_payloads"]:
        for index, item in enumerate(report["executed_payloads"], start=1):
            lines.extend(
                [
                    f"### Payload {index}: {item.get('template_id') or item.get('name') or 'Nuclei request'}",
                    "",
                    f"- Template: `{item.get('template_path') or item.get('template') or '—'}`",
                    f"- Severity: **{item.get('severity') or 'unknown'}**",
                    f"- Matched at: `{item.get('matched_at') or '—'}`",
                    f"- Host/IP: `{item.get('host') or '—'}` / `{item.get('ip') or '—'}`",
                    f"- Matcher status: `{item.get('matcher_status')}`",
                    "",
                    "Request:",
                    _fenced(item.get("request")),
                    "",
                    "Response:",
                    _fenced(item.get("response")),
                    "",
                ]
            )
    else:
        lines.extend(["No structured Nuclei request/response payload records were present.", ""])

    lines.extend(["## Assessment Council", ""])
    for round_item in report["assessment_council"]:
        rm = round_item.get("metadata", {})
        lines.extend(
            [
                f"### Round {rm.get('round')} — {rm.get('focus')}",
                "",
                f"Phase: `{rm.get('phase')}` · Subagents: {len(round_item.get('subagents', []))}",
                "",
            ]
        )
        for agent in round_item.get("subagents", []):
            am = agent.get("metadata", {})
            lines.append(f"- **{am.get('role')}** — {am.get('summary')} → `{am.get('recommended_action')}`")
        lines.append("")

    lines.extend(["## Reasoning", ""])
    for node in report["reasoning"]:
        lines.append(f"- `{node.get('metadata', {}).get('action', node['kind'])}` — {node['label']}")
    if not report["reasoning"]:
        lines.append("- No reasoning nodes recorded.")
    lines.append("")

    lines.extend(["## Raw Evidence", ""])
    for item in report["evidence"]:
        lines.extend(
            [
                f"### {item['tool']} · {item['id']}",
                "",
                f"Command: `{' '.join(item['argv'])}`",
                f"Exit code: `{item['exit_code']}`",
                "",
                "stdout:",
                _fenced(item["stdout"]),
                "",
                "stderr:",
                _fenced(item["stderr"]),
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"