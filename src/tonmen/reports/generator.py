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


def _model_calls(run: MissionRun) -> list[dict[str, Any]]:
    return [_node(node) for node in run.graph.nodes.values() if node.kind == "model.call"]


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
    model_calls = _model_calls(run)
    findings = [node for node in intelligence if node["kind"] == "intelligence.finding"]
    approval_steps = [step for step in steps if step["requires_approval"]]
    failures = [step for step in steps if step["state"] in {"failed", "denied"}]
    degraded = [step for step in steps if step["state"] == "degraded"]
    prompt_tokens = sum(int(item.get("metadata", {}).get("prompt_tokens", 0) or 0) for item in model_calls)
    output_tokens = sum(int(item.get("metadata", {}).get("output_tokens", 0) or 0) for item in model_calls)
    model_successes = sum(1 for item in model_calls if item.get("metadata", {}).get("status") == "success")
    report_gates = [_node(node) for node in run.graph.nodes.values() if node.kind == "governance.report_gate"]

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
            "model_calls": len(model_calls),
            "model_successes": model_successes,
            "model_prompt_tokens": prompt_tokens,
            "model_output_tokens": output_tokens,
        },
        "governance": {
            "execution_model": "Scope -> Guard -> Approval -> structured adapter -> shell=False Executor",
            "approval_tokens_persisted": False,
            "arbitrary_shell": False,
            "report_only": bool(report_gates) or bool(_loop_policy(run).get("report_only", False)),
            "report_gates": report_gates,
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
        "model_calls": model_calls,
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
        f"- Model calls: {summary.get('model_calls', 0)}",
        f"- Model tokens (prompt/output): {summary.get('model_prompt_tokens', 0)} / {summary.get('model_output_tokens', 0)}",
        "",
        "## Governance",
        "",
        f"- Execution model: {report['governance']['execution_model']}",
        "- Approval tokens persisted: no",
        "- Arbitrary shell: disabled",
        f"- Report only: {'yes' if report['governance'].get('report_only') else 'no'}",
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
                f"Phase: `{rm.get('phase')}` · Subagents: {len(round_item.get('subagents', []))} · Mode: `{rm.get('agent_mode', 'deterministic')}`",
                "",
            ]
        )
        for agent in round_item.get("subagents", []):
            am = agent.get("metadata", {})
            mode = am.get("agent_mode", "deterministic")
            lines.append(f"- **{am.get('role')}** [{mode}] — {am.get('summary')} → `{am.get('recommended_action')}`")
        lines.append("")

    if report.get("model_calls"):
        lines.extend(["## Model Runtime", ""])
        for item in report["model_calls"]:
            md = item.get("metadata", {})
            lines.append(
                f"- `{md.get('provider')}:{md.get('model')}` — {md.get('status')} · "
                f"tokens {md.get('prompt_tokens', 0)}/{md.get('output_tokens', 0)} · "
                f"execution authority: {md.get('execution_authority')}"
            )
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
