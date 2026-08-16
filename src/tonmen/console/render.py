from __future__ import annotations

from tonmen.missions import MissionPlan, MissionRun, MissionRunState, StepExecutionState, StepState
from tonmen.reasoning import ReasoningDecision


def render_plan(plan: MissionPlan) -> str:
    lines = [
        f"任務 Mission  {plan.id}",
        f"目標 Target   {plan.target}",
        "",
    ]
    for index, step in enumerate(plan.steps, 1):
        gate = "需審批" if step.state is StepState.WAITING_APPROVAL else "可規劃"
        lines.append(f"{index:02d}. {step.tool:<8} [{gate}]  {step.rationale}")
    return "\n".join(lines)


def render_decision(decision: ReasoningDecision) -> str:
    human = "需人決" if decision.requires_human else "可自治"
    lines = [
        f"天策 Decision  {decision.action.value}",
        f"界限 Boundary  {human}",
        f"裁決 Rationale {decision.summary}",
    ]
    if decision.basis_fact_ids:
        lines.append(f"所據 Basis      {len(decision.basis_fact_ids)} fact(s)")
    if decision.next_step_id:
        lines.append(f"所向 Next       {decision.next_step_id}")
    return "\n".join(lines)


def render_run(run: MissionRun) -> str:
    labels = {
        StepExecutionState.PENDING: "待行",
        StepExecutionState.RUNNING: "執行",
        StepExecutionState.WAITING_APPROVAL: "候旨",
        StepExecutionState.SUCCEEDED: "已成",
        StepExecutionState.SKIPPED: "止行",
        StepExecutionState.FAILED: "失敗",
        StepExecutionState.DENIED: "拒絕",
    }
    intelligence = [node for node in run.graph.nodes.values() if node.kind.startswith("intelligence.")]
    reasoning = [node for node in run.graph.nodes.values() if node.kind.startswith("reasoning.")]
    lines = [
        f"任務 Run      {run.id}",
        f"目標 Target   {run.target}",
        f"狀態 State    {run.state.value}",
        "",
    ]
    for index, step in enumerate(run.steps, 1):
        lines.append(f"{index:02d}. {step.tool:<8} [{labels[step.state]}]")
        if step.error:
            lines.append(f"    └─ {step.error}")
    lines.append("")
    lines.append(f"觀測 Observations  {len(run.observations)}")
    lines.append(f"天鑑 Intelligence  {len(intelligence)}")
    lines.append(f"天策 Decisions     {len(reasoning)}")
    lines.append(f"證據 Graph Nodes   {len(run.graph.nodes)}")
    if intelligence:
        lines.append("")
        lines.append("天鑑所見")
        for node in intelligence[:8]:
            kind = node.kind.removeprefix("intelligence.")
            severity = node.metadata.get("severity")
            prefix = f"[{severity}] " if kind == "finding" and severity else ""
            lines.append(f"  · {kind:<7} {prefix}{node.label}")
        if len(intelligence) > 8:
            lines.append(f"  · ... {len(intelligence) - 8} more")
    if reasoning:
        lines.append("")
        lines.append("天策所斷")
        for node in reasoning[-5:]:
            action = node.metadata.get("action", node.kind.removeprefix("reasoning."))
            human = "需人決" if node.metadata.get("requires_human") else "可自治"
            lines.append(f"  · {action:<16} [{human}] {node.label}")
    if run.state is MissionRunState.WAITING_APPROVAL:
        lines.append("\n天律有門：高風險步驟已停於審批界前。")
    return "\n".join(lines)
