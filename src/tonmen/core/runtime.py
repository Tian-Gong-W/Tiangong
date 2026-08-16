from __future__ import annotations

from dataclasses import dataclass

from tonmen.execution import ToolExecutor
from tonmen.jobs import JobManager
from tonmen.policy.engine import PolicyEngine
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
        runtime.executor = ToolExecutor(
            runtime.registry,
            runtime.policy,
            timeout_seconds=runtime.config.command_timeout_seconds,
        )
        runtime.jobs = JobManager(runtime.executor)
        return runtime

    def status_text(self) -> str:
        return "\n".join(
            [
                "天樞 Core        ● Online",
                "天律 Guard       ● Online",
                f"天工 Registry    ● Ready ({len(self.registry)} tools)",
                f"天行 Executor    {'● Ready' if self.executor else '○ Not loaded'}",
                f"天錄 Evidence    {'● Ready' if self.executor else '○ Not loaded'}",
                "天機 Agent       ○ Not loaded",
            ]
        )
