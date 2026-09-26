from __future__ import annotations

import os
from dataclasses import dataclass

from tonmen.ai import LeadAIOrchestrator
from tonmen.audit import AuditLog
from tonmen.events import EventBus
from tonmen.execution import ToolExecutor
from tonmen.jobs import JobManager
from tonmen.policy import ApprovalStore, PolicyEngine, TargetScope
from tonmen.tools.adapters import register_builtin_adapters
from tonmen.tools.registry import ToolRegistry
from tonmen.workers import RemoteWorkerExecutor, WorkerPool

from .config import TonmenConfig


@dataclass(slots=True)
class TonmenRuntime:
    config: TonmenConfig
    registry: ToolRegistry
    policy: PolicyEngine
    executor: ToolExecutor | RemoteWorkerExecutor | None = None
    jobs: JobManager | None = None
    approvals: ApprovalStore | None = None
    audit: AuditLog | None = None
    scope: TargetScope | None = None
    events: EventBus | None = None
    workers: WorkerPool | None = None

    @classmethod
    def genesis(cls, config: TonmenConfig | None = None, *, events: EventBus | None = None) -> "TonmenRuntime":
        config = config or TonmenConfig.default()
        if config.allow_arbitrary_shell:
            raise ValueError("TONMEN forbids arbitrary shell execution")
        return cls(config=config, registry=ToolRegistry(), policy=PolicyEngine(), events=events)

    @classmethod
    def forge(cls, config: TonmenConfig | None = None, *, events: EventBus | None = None) -> "TonmenRuntime":
        runtime = cls.genesis(config, events=events)
        register_builtin_adapters(runtime.registry)
        runtime.executor = ToolExecutor(
            runtime.registry,
            runtime.policy,
            timeout_seconds=runtime.config.command_timeout_seconds,
            tool_timeouts=dict(runtime.config.tool_timeouts),
            events=events,
        )
        runtime.jobs = JobManager(runtime.executor)
        return runtime

    @classmethod
    def sentinel(cls, config: TonmenConfig | None = None, *, events: EventBus | None = None) -> "TonmenRuntime":
        config = config or TonmenConfig.default()
        runtime = cls.genesis(config, events=events)
        register_builtin_adapters(runtime.registry)
        runtime.scope = TargetScope(config.allowed_targets, config.denied_targets)
        runtime.policy = PolicyEngine(runtime.scope)
        runtime.approvals = ApprovalStore()
        runtime.audit = AuditLog(config.workspace / "audit.jsonl")

        execution_mode = (os.getenv("TONMEN_EXECUTION_MODE") or "local").strip().lower()
        if execution_mode not in {"local", "worker"}:
            raise ValueError("TONMEN_EXECUTION_MODE must be local or worker")
        if execution_mode == "worker":
            runtime.workers = WorkerPool.from_env()
            runtime.executor = RemoteWorkerExecutor(
                runtime.registry,
                runtime.policy,
                runtime.workers,
                timeout_seconds=config.command_timeout_seconds,
                tool_timeouts=dict(config.tool_timeouts),
                approvals=runtime.approvals,
                audit=runtime.audit,
                events=events,
            )
        else:
            runtime.executor = ToolExecutor(
                runtime.registry,
                runtime.policy,
                timeout_seconds=config.command_timeout_seconds,
                tool_timeouts=dict(config.tool_timeouts),
                approvals=runtime.approvals,
                audit=runtime.audit,
                events=events,
            )
        runtime.jobs = JobManager(runtime.executor)
        return runtime

    def status_text(self) -> str:
        scope_count = len(self.scope.allowed) if self.scope else 0
        ai = LeadAIOrchestrator().public_status()
        if ai.get("active"):
            ai_state = f"● {ai.get('provider')}/{ai.get('model')}"
        elif ai.get("provider") == "openai" and not ai.get("key_configured"):
            ai_state = f"○ OpenAI key missing ({ai.get('key_env')})"
        elif ai.get("error"):
            ai_state = f"○ Disabled ({ai.get('error')})"
        else:
            ai_state = "○ Disabled"

        if isinstance(self.executor, RemoteWorkerExecutor):
            executor_state = f"● Worker Pool ({self.executor.worker_count})"
        elif self.executor is not None:
            executor_state = "● Local"
        else:
            executor_state = "○ Not loaded"

        timeout_text = ", ".join(f"{tool}={seconds}s" for tool, seconds in self.config.tool_timeouts)
        return "\n".join(
            [
                "天樞 Core        ● Online",
                "天律 Guard       ● Online",
                f"天工 Registry    ● Ready ({len(self.registry)} tools)",
                f"天域 Scope       {'● Enforced' if self.scope else '○ Not loaded'} ({scope_count} allow rules)",
                f"天契 Approval    {'● Ready' if self.approvals else '○ Not loaded'}",
                f"天錄 Audit       {'● Persistent' if self.audit else '○ Not loaded'}",
                f"天行 Executor    {executor_state}",
                f"天時 Timeouts    ● default={self.config.command_timeout_seconds}s ({timeout_text})",
                "天機 Planner      ● Ready",
                "天鑑 Intelligence ● Ready",
                "天策 Reasoner     ● Ready",
                f"主導 Lead AI     {ai_state}",
                "天衡 Mission Loop ● Ready",
            ]
        )
