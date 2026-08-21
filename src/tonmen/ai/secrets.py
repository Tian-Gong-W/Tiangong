from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Mapping


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
    if os.getenv(env_name, "").strip():
        return "environment"
    if _load(_secret_path()).get(env_name, "").strip():
        return "local_store"
    return None


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
