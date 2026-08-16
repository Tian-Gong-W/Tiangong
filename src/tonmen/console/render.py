from __future__ import annotations

from tonmen.missions import MissionPlan, StepState


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
