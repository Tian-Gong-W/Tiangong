from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class TonmenConfig:
    """Runtime configuration with conservative local defaults."""

    workspace: Path
    bind_host: str = "127.0.0.1"
    bind_port: int = 8888
    allow_arbitrary_shell: bool = False
    command_timeout_seconds: int = 120

    @classmethod
    def default(cls) -> "TonmenConfig":
        return cls(workspace=Path.cwd() / ".tonmen")
