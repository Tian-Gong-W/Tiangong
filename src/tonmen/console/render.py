from __future__ import annotations

from tonmen.missions import MissionPlan, MissionRun, MissionRunState, StepExecutionState, StepState


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


def render_run(run: MissionRun) -> str:
    labels = {
        StepExecutionState.PENDING: "待行",
        StepExecutionState.RUNNING: "執行",
        StepExecutionState.WAITING_APPROVAL: "候旨",
        StepExecutionState.SUCCEEDED: "已成",
        StepExecutionState.FAILED: "失敗",
        StepExecutionState.DENIED: "拒絕",
    }
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
    lines.append(f"證據 Graph Nodes   {len(run.graph.nodes)}")
    if run.state is MissionRunState.WAITING_APPROVAL:
        lines.append("\n天律有門：高風險步驟已停於審批界前。")
    return "\n".join(lines)
