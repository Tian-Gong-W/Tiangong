from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Mapping

from .secrets import hydrate_secret_environment

_ALLOWED_PROVIDERS = {"openai", "chatgpt", "google", "grok", "deepseek", "mistral"}
_ALLOWED_LEAD_PROVIDERS = {"disabled", "openai", "deepseek", "mistral"}
_SECRET_ENVS = ("OPENAI_API_KEY", "DEEPSEEK_API_KEY", "MISTRAL_API_KEY")


def _settings_path() -> Path:
    configured = (os.getenv("TONMEN_AI_SETTINGS_FILE") or "").strip()
    return Path(configured).expanduser() if configured else Path.home() / ".tonmen" / "ai-settings.json"


def _load(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    if path.is_symlink():
        raise ValueError("AI settings file may not be a symlink")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return dict(value) if isinstance(value, dict) else {}


def _write(path: Path, values: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(path.parent, 0o700)
    except OSError:
        pass
    if path.exists() and path.is_symlink():
        raise ValueError("AI settings file may not be a symlink")
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(dict(values), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    try:
        os.chmod(temporary, 0o600)
    except OSError:
        pass
    os.replace(temporary, path)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def get_setting(name: str, default: Any = None) -> Any:
    return _load(_settings_path()).get(name, default)


def update_settings(
    *,
    lead_enabled: bool | None = None,
    lead_provider: str | None = None,
    lead_model: str | None = None,
    pool: list[str] | None = None,
) -> dict[str, Any]:
    path = _settings_path()
    values = _load(path)

    if lead_provider is not None:
        provider = str(lead_provider).strip().lower()
        if provider not in _ALLOWED_LEAD_PROVIDERS:
            raise ValueError(f"unsupported Lead AI provider: {provider}")
        values["lead_provider"] = provider

    if lead_enabled is not None:
        if not bool(lead_enabled):
            values["lead_provider"] = "disabled"
        elif str(values.get("lead_provider") or "disabled").strip().lower() == "disabled":
            # Backward compatibility for old clients that only sent lead_enabled.
            values["lead_provider"] = "openai"

    if lead_model is not None:
        model = str(lead_model).strip()
        if not model or len(model) > 160:
            raise ValueError("Lead model name must be 1-160 characters")
        values["lead_model"] = model

    if pool is not None:
        clean: list[str] = []
        for item in pool:
            provider = str(item).strip().lower()
            if provider == "auto":
                clean = ["auto"]
                break
            if provider not in _ALLOWED_PROVIDERS:
                raise ValueError(f"unsupported AI provider: {provider}")
            if provider not in clean:
                clean.append(provider)
        values["pool"] = clean

    _write(path, values)
    return public_settings()


def public_settings() -> dict[str, Any]:
    values = _load(_settings_path())
    pool = values.get("pool", [])
    if not isinstance(pool, list):
        pool = []
    lead_provider = str(values.get("lead_provider") or "disabled").strip().lower()
    # A stored model is historical configuration, not current runtime state. When
    # Lead AI is disabled, do not project a model into the Console as if one were
    # selected or active. Re-selecting a provider can restore/set its model later.
    lead_model = str(values.get("lead_model") or "") if lead_provider != "disabled" else ""
    return {
        "lead_provider": lead_provider,
        "lead_model": lead_model,
        "pool": [str(item) for item in pool],
        "path": str(_settings_path()),
        "secret_values_exposed": False,
    }


def apply_local_ai_environment() -> None:
    """Hydrate local Console settings without overriding explicit process env."""
    settings = public_settings()
    if not os.getenv("TONMEN_AI_PROVIDER", "").strip():
        os.environ["TONMEN_AI_PROVIDER"] = str(settings["lead_provider"])
    if not os.getenv("TONMEN_AI_MODEL", "").strip():
        model = str(settings["lead_model"] or "").strip()
        if model:
            os.environ["TONMEN_AI_MODEL"] = model
    if not os.getenv("TONMEN_AI_POOL", "").strip():
        pool = [str(item) for item in settings.get("pool", []) if str(item).strip()]
        if pool:
            os.environ["TONMEN_AI_POOL"] = ",".join(pool)
    for env_name in _SECRET_ENVS:
        hydrate_secret_environment(env_name)
