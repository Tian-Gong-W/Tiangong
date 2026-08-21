from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Mapping

_HYDRATED_ENV: set[str] = set()


def _secret_path() -> Path:
    configured = (os.getenv("TONMEN_AI_SECRETS_FILE") or "").strip()
    return Path(configured).expanduser() if configured else Path.home() / ".tonmen" / "secrets.json"


def _load(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    if path.is_symlink():
        raise ValueError("AI secrets file may not be a symlink")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(raw, dict):
        return {}
    return {
        str(key): str(value)
        for key, value in raw.items()
        if isinstance(key, str) and isinstance(value, str) and value.strip()
    }


def _write(path: Path, values: Mapping[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(path.parent, 0o700)
    except OSError:
        pass
    if path.exists() and path.is_symlink():
        raise ValueError("AI secrets file may not be a symlink")
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


def get_secret(env_name: str) -> str:
    env_value = os.getenv(env_name, "").strip()
    if env_value:
        return env_value
    return _load(_secret_path()).get(env_name, "").strip()


def secret_source(env_name: str) -> str | None:
    env_value = os.getenv(env_name, "").strip()
    stored = _load(_secret_path()).get(env_name, "").strip()
    if env_value and env_name not in _HYDRATED_ENV:
        return "environment"
    if stored:
        return "local_store"
    if env_value:
        return "environment"
    return None


def hydrate_secret_environment(env_name: str) -> bool:
    if os.getenv(env_name, "").strip() and env_name not in _HYDRATED_ENV:
        return False
    value = _load(_secret_path()).get(env_name, "").strip()
    if not value:
        return False
    os.environ[env_name] = value
    _HYDRATED_ENV.add(env_name)
    return True


def clear_hydrated_secret_environment(env_name: str) -> None:
    if env_name in _HYDRATED_ENV:
        os.environ.pop(env_name, None)
        _HYDRATED_ENV.discard(env_name)


def set_secret(env_name: str, value: str) -> None:
    clean = str(value).strip()
    if not clean:
        raise ValueError("secret value is empty")
    if len(clean.encode("utf-8")) > 16384:
        raise ValueError("secret value is too large")
    path = _secret_path()
    values = _load(path)
    values[env_name] = clean
    _write(path, values)


def clear_secret(env_name: str) -> bool:
    path = _secret_path()
    values = _load(path)
    removed = values.pop(env_name, None) is not None
    if removed:
        _write(path, values)
    return removed


def public_secret_status(env_name: str) -> dict[str, object]:
    source = secret_source(env_name)
    return {
        "configured": source is not None,
        "source": source,
        "persisted_by_tonmen": source == "local_store",
        "value_exposed": False,
        "path": str(_secret_path()) if source == "local_store" else None,
    }
