from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class TonmenConfig:
    """Runtime configuration with deny-by-default external scope."""

    workspace: Path
    bind_host: str = "127.0.0.1"
    bind_port: int = 8888
    allow_arbitrary_shell: bool = False
    command_timeout_seconds: int = 120
    allowed_targets: tuple[str, ...] = ("127.0.0.1", "::1", "localhost")
    denied_targets: tuple[str, ...] = ()

    @classmethod
    def default(cls) -> "TonmenConfig":
        return cls(workspace=Path.cwd() / ".tonmen")
