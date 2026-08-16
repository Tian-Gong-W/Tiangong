from __future__ import annotations

import argparse

from .agents import MissionCoordinator, MissionPlanner, MissionPlanningDenied, MissionRunDenied
from .console import render_plan, render_run
from .core.runtime import TonmenRuntime

BANNER = """\
╔══════════════════════════════════════════════╗
║              雲 頂 天 宮                    ║
║              TONMEN Mission                ║
║              by Top-Men AI                 ║
╚══════════════════════════════════════════════╝
"""


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tonmen")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("status", help="show governed runtime status")
    plan = sub.add_parser("plan", help="create a dry-run mission plan for an authorized target")
    plan.add_argument("target")
    run = sub.add_parser("run", help="execute autonomous discovery steps and stop at approval boundaries")
    run.add_argument("target")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    runtime = TonmenRuntime.sentinel()
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
        print(render_run(mission_run))
        return 0 if mission_run.state.value in {"succeeded", "waiting_approval"} else 3
    return 1
