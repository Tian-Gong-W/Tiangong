from __future__ import annotations

import argparse
from pathlib import Path

from .agents import MissionCoordinator, MissionPlanner, MissionPlanningDenied, MissionRunDenied
from .chronicle import ChronicleStore
from .console import render_decision, render_loop, render_plan, render_run
from .core.config import TonmenConfig
from .core.runtime import TonmenRuntime
from .doctor import render_doctor, run_doctor
from .loop import LoopStopReason, MissionLoop, MissionLoopPolicy
from .missions import MissionRunState, StepExecutionState
from .policy import validate_scope_rule
from .reasoning import MissionReasoner

BANNER = """\
╔══════════════════════════════════════════════╗
║              雲 頂 天 宮                    ║
║              TONMEN Alpha                  ║
║              by Top-Men AI                 ║
╚══════════════════════════════════════════════╝
"""


def _add_loop_budget_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--max-iterations", type=int, default=8)
    parser.add_argument("--max-executions", type=int, default=3)
    parser.add_argument("--max-repeat-decisions", type=int, default=2)
    parser.add_argument("--max-duration", type=int, default=300, dest="max_duration_seconds")


def _loop_policy(args) -> MissionLoopPolicy:
    return MissionLoopPolicy(
        max_iterations=args.max_iterations,
        max_executions=args.max_executions,
        max_repeat_decisions=args.max_repeat_decisions,
        max_duration_seconds=args.max_duration_seconds,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tonmen")
    parser.add_argument(
        "--config",
        type=Path,
        help="project config path (default: ./tonmen.toml)",
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("status", help="show governed runtime status")
    sub.add_parser("doctor", help="check runtime dependencies and project readiness")

    init = sub.add_parser("init", help="create a local tonmen.toml with safe defaults")
    init.add_argument("--force", action="store_true", help="replace an existing config file")

    scope = sub.add_parser("scope", help="manage explicitly authorized target scope")
    scope_sub = scope.add_subparsers(dest="scope_command", required=True)
    scope_sub.add_parser("show", help="show allowed and denied target rules")
    scope_add = scope_sub.add_parser("add", help="add an authorized host, IP/CIDR, or *.domain rule")
    scope_add.add_argument("target")
    scope_remove = scope_sub.add_parser("remove", help="remove a non-default allowed target rule")
    scope_remove.add_argument("target")

    plan = sub.add_parser("plan", help="create a dry-run mission plan for an authorized target")
    plan.add_argument("target")
    run = sub.add_parser("run", help="execute the current governed mission to its next boundary")
    run.add_argument("target")
    loop = sub.add_parser("loop", help="run a bounded observe-reason-act mission loop")
    loop.add_argument("target")
    _add_loop_budget_arguments(loop)
    loop_resume = sub.add_parser("loop-resume", help="continue a non-terminal persisted loop with a fresh bounded budget")
    loop_resume.add_argument("run_id")
    _add_loop_budget_arguments(loop_resume)
    sub.add_parser("missions", help="list persisted mission runs")
    show = sub.add_parser("show", help="show a persisted mission run")
    show.add_argument("run_id")
    reason = sub.add_parser("reason", help="explain the current evidence-backed mission decision")
    reason.add_argument("run_id")
    resume = sub.add_parser("resume", help="resume a persisted mission at its approval boundary")
    resume.add_argument("run_id")
    resume.add_argument("--approve", action="store_true", help="explicitly approve the current waiting step")
    return parser


def _waiting_step(plan, run):
    for planned, execution in zip(plan.steps, run.steps, strict=True):
        if execution.state is StepExecutionState.WAITING_APPROVAL:
            return planned
    return None


def _print_loop_result(result) -> None:
    print(render_run(result.run))
    print("")
    print(render_loop(result))


def _load_config(path: Path | None) -> TonmenConfig:
    return TonmenConfig.default(path)


def _scope_show(config: TonmenConfig) -> None:
    path = config.config_path or Path.cwd() / "tonmen.toml"
    print(f"配置 Config   {path}")
    print("允許 Allowed")
    for rule in config.allowed_targets:
        marker = " (default)" if rule in {"127.0.0.1", "::1", "localhost"} else ""
        print(f"  + {rule}{marker}")
    print("拒絕 Denied")
    if config.denied_targets:
        for rule in config.denied_targets:
            print(f"  - {rule}")
    else:
        print("  (none)")


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    print(BANNER)

    try:
        config = _load_config(args.config)
    except (OSError, ValueError) as exc:
        print(f"配置拒絕: {exc}")
        return 2

    if args.command == "init":
        path = config.config_path or Path.cwd() / "tonmen.toml"
        if path.exists() and not args.force:
            print(f"配置已存在: {path}")
            print("如需覆寫，使用 tonmen init --force")
            return 2
        saved = config.save(path)
        print(f"天冊配置已立: {saved}")
        print("默认仅授权 localhost；使用 `tonmen scope add <authorized-target>` 明示扩展范围。")
        return 0

    if args.command == "scope":
        if args.scope_command == "show":
            _scope_show(config)
            return 0
        try:
            rule = validate_scope_rule(args.target)
            updated = (
                config.with_allowed_target(rule)
                if args.scope_command == "add"
                else config.without_allowed_target(rule)
            )
            saved = updated.save()
        except (OSError, ValueError) as exc:
            print(f"天域拒絕: {exc}")
            return 2
        verb = "已納入" if args.scope_command == "add" else "已移除"
        print(f"天域 {verb}: {rule}")
        print(f"配置已寫入: {saved}")
        return 0

    if args.command == "doctor":
        report = run_doctor(config)
        print(render_doctor(report))
        return 0 if report.ready else 3

    runtime = TonmenRuntime.sentinel(config)
    chronicle = ChronicleStore(runtime.config.workspace)

    if args.command in (None, "status"):
        print(runtime.status_text())
        print("\n人予其意，宮成其事。")
        return 0

    if args.command in {"plan", "run", "loop"}:
        try:
            plan = MissionPlanner(runtime).plan(args.target)
        except MissionPlanningDenied as exc:
            print(f"天律拒絕: {exc}")
            print("若这是你明确授权的目标，先执行: tonmen scope add <target>")
            return 2

        if args.command == "plan":
            print(render_plan(plan))
            return 0

        if args.command == "run":
            try:
                mission_run = MissionCoordinator(runtime).run(plan)
            except MissionRunDenied as exc:
                print(f"天律拒絕: {exc}")
                return 2
            chronicle.save(plan, mission_run)
            print(render_run(mission_run))
            print(f"\n天冊已錄: {mission_run.id}")
            return 0 if mission_run.state in {MissionRunState.SUCCEEDED, MissionRunState.WAITING_APPROVAL} else 3

        try:
            result = MissionLoop(runtime, _loop_policy(args)).run(plan)
        except (MissionRunDenied, ValueError) as exc:
            print(f"天衡拒絕: {exc}")
            return 2
        chronicle.save(plan, result.run)
        _print_loop_result(result)
        print(f"\n天冊已錄: {result.run.id}")
        return 3 if result.stop_reason is LoopStopReason.TERMINAL else 0

    if args.command == "missions":
        entries = chronicle.list()
        if not entries:
            print("天冊無錄。")
            return 0
        for entry in entries:
            print(f"{entry.run_id}  {entry.state.value:<18}  {entry.target}")
        return 0

    if args.command in {"show", "reason"}:
        try:
            plan, mission_run = chronicle.load(args.run_id)
        except (FileNotFoundError, ValueError) as exc:
            print(f"天冊無此錄: {exc}")
            return 2
        if args.command == "show":
            print(render_run(mission_run))
        else:
            print(render_decision(MissionReasoner().decide(plan, mission_run)))
        return 0

    if args.command == "loop-resume":
        try:
            plan, mission_run = chronicle.load(args.run_id)
        except (FileNotFoundError, ValueError) as exc:
            print(f"天冊無此錄: {exc}")
            return 2
        if mission_run.state is not MissionRunState.RUNNING:
            print("此任務不可無授權續行；若在候旨狀態，請使用 resume --approve。")
            return 2
        try:
            result = MissionLoop(runtime, _loop_policy(args)).resume(plan, mission_run)
        except (MissionRunDenied, ValueError) as exc:
            print(f"天衡拒絕: {exc}")
            return 2
        chronicle.save(plan, result.run)
        _print_loop_result(result)
        return 3 if result.stop_reason is LoopStopReason.TERMINAL else 0

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
            result = MissionLoop(runtime).resume(
                plan,
                mission_run,
                approval_tokens={waiting.id: grant.token},
            )
        except (MissionRunDenied, ValueError) as exc:
            print(f"天律拒絕: {exc}")
            return 2
        chronicle.save(plan, result.run)
        _print_loop_result(result)
        return 3 if result.stop_reason is LoopStopReason.TERMINAL else 0

    return 1
