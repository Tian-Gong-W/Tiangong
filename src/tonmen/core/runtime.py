from __future__ import annotations

from dataclasses import dataclass

from tonmen.policy.engine import PolicyEngine
from tonmen.tools.registry import ToolRegistry

from .config import TonmenConfig


@dataclass(slots=True)
class TonmenRuntime:
    config: TonmenConfig
    registry: ToolRegistry
    policy: PolicyEngine

    @classmethod
    def genesis(cls, config: TonmenConfig | None = None) -> "TonmenRuntime":
        config = config or TonmenConfig.default()
        if config.allow_arbitrary_shell:
            raise ValueError("TONMEN Genesis forbids arbitrary shell execution")
        return cls(config=config, registry=ToolRegistry(), policy=PolicyEngine())

    def status_text(self) -> str:
        return "\n".join(
            [
                "天樞 Core        ● Online",
                "天律 Guard       ● Online",
                f"天工 Registry    ● Ready ({len(self.registry)} tools)",
                "天機 Agent       ○ Not loaded",
            ]
        )
