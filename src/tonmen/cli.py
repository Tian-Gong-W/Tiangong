from __future__ import annotations

import argparse

from .agents import MissionCoordinator, MissionPlanner, MissionPlanningDenied, MissionRunDenied
from .chronicle import ChronicleStore
from .console import render_plan, render_run
from .core.runtime import TonmenRuntime
from .missions import MissionRunState, StepExecutionState

BANNER = """\
╔══════════════════════════════════════════════╗
║              雲 頂 天 宮                    ║
║              TONMEN Intelligence           ║
║              by Top-Men AI                 ║
╚══════════════════════════════════════════════╝
"""


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tonmen")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("status", help="show governed runtime status")
    plan = sub.add_parser("plan", help="create a dry-run mission plan for an authorized target")
    plan.add_argument("target")
    run = sub.add_parser("run", help="execute autonomous discovery steps and persist the mission")
    run.add_argument("target")
    sub.add_parser("missions", help="list persisted mission runs")
    show = sub.add_parser("show", help="show a persisted mission run")
    show.add_argument("run_id")
    resume = sub.add_parser("resume", help="resume a persisted mission at its approval boundary")
    resume.add_argument("run_id")
    resume.add_argument("--approve", action="store_true", help="explicitly approve the current waiting step")
    return parser


def _waiting_step(plan, run):
    for planned, execution in zip(plan.steps, run.steps, strict=True):
        if execution.state is StepExecutionState.WAITING_APPROVAL:
            return planned
    return None


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    runtime = TonmenRuntime.sentinel()
    chronicle = ChronicleStore(runtime.config.workspace)
    print(BANNER)
    if args.command in (None, "status"):
        print(runtime.status_text())
        print("\n人予其意，宮成其事。")
        return 0
    if args.command in {"plan", "run"}:
        try:
            plan = MissionPlanner(runtime).plan(args.target)
        except MissionPlanningDenied as exc:
            print(f"天律拒絕: {exc}")
            return 2
        if args.command == "plan":
            print(render_plan(plan))
            return 0
        try:
            mission_run = MissionCoordinator(runtime).run(plan)
        except MissionRunDenied as exc:
            print(f"天律拒絕: {exc}")
            return 2
        chronicle.save(plan, mission_run)
        print(render_run(mission_run))
        print(f"\n天冊已錄: {mission_run.id}")
        return 0 if mission_run.state in {MissionRunState.SUCCEEDED, MissionRunState.WAITING_APPROVAL} else 3
    if args.command == "missions":
        entries = chronicle.list()
        if not entries:
            print("天冊無錄。")
            return 0
        for entry in entries:
            print(f"{entry.run_id}  {entry.state.value:<18}  {entry.target}")
        return 0
    if args.command == "show":
        try:
            _, mission_run = chronicle.load(args.run_id)
        except (FileNotFoundError, ValueError) as exc:
            print(f"天冊無此錄: {exc}")
            return 2
        print(render_run(mission_run))
        return 0
    if args.command == "resume":
        try:
            plan, mission_run = chronicle.load(args.run_id)
        except (FileNotFoundError, ValueError) as exc:
            print(f"天冊無此錄: {exc}")
            return 2
        if mission_run.state is not MissionRunState.WAITING_APPROVAL:
            print("此任務不在候旨狀態。")
            return 2
        waiting = _waiting_step(plan, mission_run)
        if waiting is None:
            print("候旨步驟不存在，拒絕續行。")
            return 2
        if not args.approve:
            print(render_run(mission_run))
            print("\n需由人明示 --approve 方可越過此審批門。")
            return 4
        if runtime.approvals is None:
            print("天契未載入，拒絕續行。")
            return 2
        grant = runtime.approvals.issue(tool=waiting.tool, target=waiting.target)
        try:
            MissionCoordinator(runtime).resume(plan, mission_run, approval_tokens={waiting.id: grant.token})
        except MissionRunDenied as exc:
            print(f"天律拒絕: {exc}")
            return 2
        chronicle.save(plan, mission_run)
        print(render_run(mission_run))
        return 0 if mission_run.state in {MissionRunState.SUCCEEDED, MissionRunState.WAITING_APPROVAL} else 3
    return 1
