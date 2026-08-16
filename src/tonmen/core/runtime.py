from __future__ import annotations

from dataclasses import dataclass

from tonmen.audit import AuditLog
from tonmen.execution import ToolExecutor
from tonmen.jobs import JobManager
from tonmen.policy import ApprovalStore, PolicyEngine, TargetScope
from tonmen.tools.adapters import register_builtin_adapters
from tonmen.tools.registry import ToolRegistry

from .config import TonmenConfig


@dataclass(slots=True)
class TonmenRuntime:
    config: TonmenConfig
    registry: ToolRegistry
    policy: PolicyEngine
    executor: ToolExecutor | None = None
    jobs: JobManager | None = None
    approvals: ApprovalStore | None = None
    audit: AuditLog | None = None
    scope: TargetScope | None = None

    @classmethod
    def genesis(cls, config: TonmenConfig | None = None) -> "TonmenRuntime":
        config = config or TonmenConfig.default()
        if config.allow_arbitrary_shell:
            raise ValueError("TONMEN forbids arbitrary shell execution")
        return cls(config=config, registry=ToolRegistry(), policy=PolicyEngine())

    @classmethod
    def forge(cls, config: TonmenConfig | None = None) -> "TonmenRuntime":
        runtime = cls.genesis(config)
        register_builtin_adapters(runtime.registry)
        runtime.executor = ToolExecutor(runtime.registry, runtime.policy, timeout_seconds=runtime.config.command_timeout_seconds)
        runtime.jobs = JobManager(runtime.executor)
        return runtime

    @classmethod
    def sentinel(cls, config: TonmenConfig | None = None) -> "TonmenRuntime":
        config = config or TonmenConfig.default()
        runtime = cls.genesis(config)
        register_builtin_adapters(runtime.registry)
        runtime.scope = TargetScope(config.allowed_targets, config.denied_targets)
        runtime.policy = PolicyEngine(runtime.scope)
        runtime.approvals = ApprovalStore()
        runtime.audit = AuditLog(config.workspace / "audit.jsonl")
        runtime.executor = ToolExecutor(
            runtime.registry,
            runtime.policy,
            timeout_seconds=config.command_timeout_seconds,
            approvals=runtime.approvals,
            audit=runtime.audit,
        )
        runtime.jobs = JobManager(runtime.executor)
        return runtime

    def status_text(self) -> str:
        return "\n".join(
            [
                "天樞 Core        ● Online",
                "天律 Guard       ● Online",
                f"天工 Registry    ● Ready ({len(self.registry)} tools)",
                f"天域 Scope       {'● Enforced' if self.scope else '○ Not loaded'}",
                f"天契 Approval    {'● Ready' if self.approvals else '○ Not loaded'}",
                f"天錄 Audit       {'● Persistent' if self.audit else '○ Not loaded'}",
                f"天行 Executor    {'● Ready' if self.executor else '○ Not loaded'}",
                "天機 Agent       ○ Not loaded",
            ]
        )
