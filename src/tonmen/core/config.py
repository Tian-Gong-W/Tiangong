from __future__ import annotations

import json
import os
from dataclasses import dataclass, replace
from pathlib import Path
from urllib.parse import urlparse

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib

CONFIG_FILENAME = "tonmen.toml"
DEFAULT_ALLOWED_TARGETS = ("127.0.0.1", "::1", "localhost")
DEFAULT_AI_BASE_URL = "http://127.0.0.1:11434"
_AI_LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}
_AI_PROVIDERS = {"none", "ollama"}


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


def validate_local_ai_base_url(value: str) -> str:
    """Allow local AI traffic only to a plain-HTTP loopback origin."""
    text = str(value).strip().rstrip("/")
    parsed = urlparse(text)
    if parsed.scheme != "http":
        raise ValueError("local AI base_url must use http on loopback")
    if (parsed.hostname or "").lower() not in _AI_LOOPBACK_HOSTS:
        raise ValueError("local AI base_url must target loopback only")
    if parsed.username or parsed.password:
        raise ValueError("local AI base_url must not contain credentials")
    if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        raise ValueError("local AI base_url must be an origin without path/query/fragment")
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("local AI base_url has an invalid port") from exc
    if port is not None and not 1 <= port <= 65535:
        raise ValueError("local AI base_url port must be within 1-65535")
    return text


@dataclass(frozen=True, slots=True)
class TonmenConfig:
    """Runtime configuration with deny-by-default external scope."""

    workspace: Path
    bind_host: str = "127.0.0.1"
    bind_port: int = 8888
    allow_arbitrary_shell: bool = False
    command_timeout_seconds: int = 120
    allowed_targets: tuple[str, ...] = DEFAULT_ALLOWED_TARGETS
    denied_targets: tuple[str, ...] = ()
    ai_enabled: bool = False
    ai_provider: str = "none"
    ai_model: str = ""
    ai_base_url: str = DEFAULT_AI_BASE_URL
    ai_timeout_seconds: int = 20
    config_path: Path | None = None

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
        ai = data.get("ai", {})
        if not isinstance(runtime, dict) or not isinstance(scope, dict) or not isinstance(ai, dict):
            raise ValueError("tonmen.toml sections must be tables")

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
        if timeout <= 0:
            raise ValueError("command_timeout_seconds must be positive")
        if not 1 <= bind_port <= 65535:
            raise ValueError("bind_port must be within 1-65535")

        ai_enabled = bool(ai.get("enabled", False))
        ai_provider = str(ai.get("provider", "none")).strip().lower() or "none"
        if ai_provider not in _AI_PROVIDERS:
            raise ValueError("ai.provider must be one of: none, ollama")
        ai_model = str(ai.get("model", "")).strip()
        ai_base_url = validate_local_ai_base_url(str(ai.get("base_url", DEFAULT_AI_BASE_URL)))
        ai_timeout = int(ai.get("timeout_seconds", 20))
        if not 1 <= ai_timeout <= 120:
            raise ValueError("ai.timeout_seconds must be between 1 and 120")
        if ai_enabled and ai_provider != "ollama":
            raise ValueError("enabled local AI currently requires provider = 'ollama'")
        if ai_enabled and not ai_model:
            raise ValueError("enabled local AI requires ai.model")

        return cls(
            workspace=workspace,
            bind_host=str(runtime.get("bind_host", "127.0.0.1")),
            bind_port=bind_port,
            allow_arbitrary_shell=False,
            command_timeout_seconds=timeout,
            allowed_targets=allowed,
            denied_targets=denied,
            ai_enabled=ai_enabled,
            ai_provider=ai_provider,
            ai_model=ai_model,
            ai_base_url=ai_base_url,
            ai_timeout_seconds=ai_timeout,
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
                "[scope]",
                f"allowed_targets = {_toml_array(_normalize_rules(self.allowed_targets))}",
                f"denied_targets = {_toml_array(_normalize_rules(self.denied_targets))}",
                "",
                "[ai]",
                "# Optional local advisory model. No API key is required or stored.",
                f"enabled = {'true' if self.ai_enabled else 'false'}",
                f"provider = {json.dumps(self.ai_provider, ensure_ascii=False)}",
                f"model = {json.dumps(self.ai_model, ensure_ascii=False)}",
                f"base_url = {json.dumps(validate_local_ai_base_url(self.ai_base_url), ensure_ascii=False)}",
                f"timeout_seconds = {self.ai_timeout_seconds}",
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
