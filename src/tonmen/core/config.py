from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, replace
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib

CONFIG_FILENAME = "tonmen.toml"
DEFAULT_ALLOWED_TARGETS = ("127.0.0.1", "::1", "localhost")
DEFAULT_TOOL_TIMEOUTS = (("nmap", 300), ("httpx", 120), ("nuclei", 240))
_TOOL_NAME = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")


def _normalize_rules(values) -> tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        rule = str(value).strip().lower()
        if rule and rule not in seen:
            seen.add(rule)
            ordered.append(rule)
    return tuple(ordered)


def _toml_array(values: tuple[str, ...]) -> str:
    return "[" + ", ".join(json.dumps(item, ensure_ascii=False) for item in values) + "]"


def _normalize_tool_timeouts(values) -> tuple[tuple[str, int], ...]:
    merged = {name: seconds for name, seconds in DEFAULT_TOOL_TIMEOUTS}
    for raw_name, raw_seconds in values:
        name = str(raw_name).strip().lower()
        if not _TOOL_NAME.fullmatch(name):
            raise ValueError(f"invalid tool timeout name: {raw_name}")
        seconds = int(raw_seconds)
        if not 1 <= seconds <= 7200:
            raise ValueError(f"tool timeout for {name} must be within 1-7200 seconds")
        merged[name] = seconds
    return tuple(sorted(merged.items()))


@dataclass(frozen=True, slots=True)
class TonmenConfig:
    """Runtime configuration with deny-by-default external scope."""

    workspace: Path
    bind_host: str = "127.0.0.1"
    bind_port: int = 8888
    allow_arbitrary_shell: bool = False
    command_timeout_seconds: int = 120
    tool_timeouts: tuple[tuple[str, int], ...] = DEFAULT_TOOL_TIMEOUTS
    allowed_targets: tuple[str, ...] = DEFAULT_ALLOWED_TARGETS
    denied_targets: tuple[str, ...] = ()
    config_path: Path | None = None

    def timeout_for(self, tool: str) -> int:
        name = str(tool).strip().lower()
        for configured_tool, seconds in self.tool_timeouts:
            if configured_tool == name:
                return int(seconds)
        return int(self.command_timeout_seconds)

    @property
    def max_command_timeout_seconds(self) -> int:
        values = [int(self.command_timeout_seconds), *(int(seconds) for _, seconds in self.tool_timeouts)]
        return max(values)

    @classmethod
    def default(cls, config_path: Path | str | None = None) -> "TonmenConfig":
        path = Path(config_path).expanduser() if config_path else Path.cwd() / CONFIG_FILENAME
        path = path.resolve()
        if path.exists():
            return cls.load(path)
        return cls(workspace=(path.parent / ".tonmen").resolve(), config_path=path)

    @classmethod
    def load(cls, path: Path | str) -> "TonmenConfig":
        config_path = Path(path).expanduser().resolve()
        data = tomllib.loads(config_path.read_text(encoding="utf-8"))
        runtime = data.get("tonmen", {})
        scope = data.get("scope", {})
        timeouts = data.get("timeouts", {})
        if not isinstance(runtime, dict) or not isinstance(scope, dict) or not isinstance(timeouts, dict):
            raise ValueError("tonmen.toml tonmen/scope/timeouts sections must be tables")

        allow_arbitrary_shell = bool(runtime.get("allow_arbitrary_shell", False))
        if allow_arbitrary_shell:
            raise ValueError("TONMEN forbids arbitrary shell execution")

        workspace_value = Path(str(runtime.get("workspace", ".tonmen"))).expanduser()
        workspace = workspace_value if workspace_value.is_absolute() else config_path.parent / workspace_value
        workspace = workspace.resolve()

        configured_allowed = scope.get("allowed_targets", [])
        configured_denied = scope.get("denied_targets", [])
        if not isinstance(configured_allowed, list) or not isinstance(configured_denied, list):
            raise ValueError("scope target rules must be TOML arrays")

        allowed = _normalize_rules((*DEFAULT_ALLOWED_TARGETS, *configured_allowed))
        denied = _normalize_rules(configured_denied)

        timeout = int(runtime.get("command_timeout_seconds", 120))
        bind_port = int(runtime.get("bind_port", 8888))
        if not 1 <= timeout <= 7200:
            raise ValueError("command_timeout_seconds must be within 1-7200 seconds")
        if not 1 <= bind_port <= 65535:
            raise ValueError("bind_port must be within 1-65535")
        tool_timeouts = _normalize_tool_timeouts(timeouts.items())

        return cls(
            workspace=workspace,
            bind_host=str(runtime.get("bind_host", "127.0.0.1")),
            bind_port=bind_port,
            allow_arbitrary_shell=False,
            command_timeout_seconds=timeout,
            tool_timeouts=tool_timeouts,
            allowed_targets=allowed,
            denied_targets=denied,
            config_path=config_path,
        )

    def with_allowed_target(self, target: str) -> "TonmenConfig":
        return replace(self, allowed_targets=_normalize_rules((*self.allowed_targets, target)))

    def without_allowed_target(self, target: str) -> "TonmenConfig":
        rule = str(target).strip().lower()
        if rule in DEFAULT_ALLOWED_TARGETS:
            raise ValueError(f"default loopback scope cannot be removed: {rule}")
        if rule not in self.allowed_targets:
            raise ValueError(f"scope rule is not allowed: {rule}")
        return replace(self, allowed_targets=tuple(item for item in self.allowed_targets if item != rule))

    def save(self, path: Path | str | None = None) -> Path:
        target = Path(path).expanduser() if path else (self.config_path or Path.cwd() / CONFIG_FILENAME)
        target = target.resolve()
        target.parent.mkdir(parents=True, exist_ok=True)

        try:
            workspace_text = str(self.workspace.resolve().relative_to(target.parent))
        except ValueError:
            workspace_text = str(self.workspace.resolve())

        normalized_timeouts = _normalize_tool_timeouts(self.tool_timeouts)
        timeout_lines = [f"{name} = {seconds}" for name, seconds in normalized_timeouts]
        content = "\n".join(
            [
                "# TONMEN project configuration",
                "# Add only targets you are explicitly authorized to assess.",
                "",
                "[tonmen]",
                f"workspace = {json.dumps(workspace_text, ensure_ascii=False)}",
                f"bind_host = {json.dumps(self.bind_host, ensure_ascii=False)}",
                f"bind_port = {self.bind_port}",
                f"command_timeout_seconds = {self.command_timeout_seconds}",
                "allow_arbitrary_shell = false",
                "",
                "# Per-tool execution ceilings override command_timeout_seconds.",
                "# Keep mission time budgets above the longest enabled tool timeout.",
                "[timeouts]",
                *timeout_lines,
                "",
                "[scope]",
                f"allowed_targets = {_toml_array(_normalize_rules(self.allowed_targets))}",
                f"denied_targets = {_toml_array(_normalize_rules(self.denied_targets))}",
                "",
            ]
        )

        temporary = target.with_name(f".{target.name}.tmp")
        temporary.write_text(content, encoding="utf-8")
        try:
            os.chmod(temporary, 0o600)
        except OSError:
            pass
        os.replace(temporary, target)
        return target
