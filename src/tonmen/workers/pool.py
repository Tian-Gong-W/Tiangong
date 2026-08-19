from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

from tonmen.tools import ToolRequest

from .protocol import normalize_worker_id, require_worker_secret

_ENV_RE = re.compile(r"^[A-Z_][A-Z0-9_]*$")


@dataclass(frozen=True, slots=True)
class WorkerSpec:
    id: str
    url: str
    region: str = "default"
    tags: tuple[str, ...] = ()
    secret_env: str = "TONMEN_WORKER_SECRET"
    weight: float = 1.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", normalize_worker_id(self.id))
        parsed = urlparse(self.url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError(f"worker {self.id} URL must be http(s)://host[:port]")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError(f"worker {self.id} URL must not contain credentials, query, or fragment")
        if parsed.path not in {"", "/"}:
            raise ValueError(f"worker {self.id} URL must not contain an application path")
        region = str(self.region or "default").strip().lower()
        object.__setattr__(self, "region", region or "default")
        object.__setattr__(self, "tags", tuple(dict.fromkeys(str(item).strip().lower() for item in self.tags if str(item).strip())))
        secret_env = str(self.secret_env or "TONMEN_WORKER_SECRET").strip().upper()
        if not _ENV_RE.fullmatch(secret_env):
            raise ValueError(f"worker {self.id} secret_env is not a valid environment variable name")
        object.__setattr__(self, "secret_env", secret_env)
        if float(self.weight) <= 0:
            raise ValueError("worker weight must be positive")
        object.__setattr__(self, "weight", float(self.weight))

    @property
    def base_url(self) -> str:
        return self.url.rstrip("/")

    @property
    def secret_configured(self) -> bool:
        value = os.getenv(self.secret_env, "")
        return len(value.encode("utf-8")) >= 32

    def secret(self) -> str:
        return require_worker_secret(os.getenv(self.secret_env, ""))

    def public_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "url": self.url,
            "region": self.region,
            "tags": list(self.tags),
            "weight": self.weight,
            "secret_env": self.secret_env,
            "secret_configured": self.secret_configured,
            "secret_value_exposed": False,
        }


@dataclass(slots=True)
class WorkerState:
    calls: int = 0
    failures: int = 0
    last_error: str | None = None
    last_health: dict[str, Any] | None = None


class WorkerPool:
    """Configured worker fleet. Selection never changes Scope or tool semantics."""

    def __init__(self, workers: tuple[WorkerSpec, ...] = ()) -> None:
        ids = [item.id for item in workers]
        if len(ids) != len(set(ids)):
            raise ValueError("worker ids must be unique")
        self.workers = workers
        self.state = {item.id: WorkerState() for item in workers}

    @classmethod
    def from_env(cls) -> "WorkerPool":
        """Parse TONMEN_WORKERS without embedding secret values.

        Syntax (semicolon-separated):
          id@https://host:8890#region=uae#tags=nmap,nuclei#secret_env=TONMEN_WORKER_SECRET_UAE#weight=2
        """
        raw = os.getenv("TONMEN_WORKERS", "").strip()
        if not raw:
            return cls(())
        workers: list[WorkerSpec] = []
        for chunk in raw.split(";"):
            value = chunk.strip()
            if not value:
                continue
            identity, sep, remainder = value.partition("@")
            if not sep:
                raise ValueError("TONMEN_WORKERS entries must use id@url syntax")
            url, *options = remainder.split("#")
            opts: dict[str, str] = {}
            for option in options:
                key, eq, option_value = option.partition("=")
                if not eq:
                    raise ValueError(f"invalid worker option: {option}")
                opts[key.strip().lower()] = option_value.strip()
            tags = tuple(item.strip() for item in opts.get("tags", "").split(",") if item.strip())
            workers.append(
                WorkerSpec(
                    id=identity,
                    url=url.strip(),
                    region=opts.get("region", "default"),
                    tags=tags,
                    secret_env=opts.get("secret_env", "TONMEN_WORKER_SECRET"),
                    weight=float(opts.get("weight", "1") or "1"),
                )
            )
        return cls(tuple(workers))

    def get(self, worker_id: str) -> WorkerSpec:
        normalized = normalize_worker_id(worker_id)
        for item in self.workers:
            if item.id == normalized:
                return item
        raise KeyError(normalized)

    def candidates(self, request: ToolRequest) -> tuple[WorkerSpec, ...]:
        preferred_id = str(request.context.get("worker_id") or os.getenv("TONMEN_WORKER_ID", "")).strip().lower()
        preferred_region = str(request.context.get("worker_region") or os.getenv("TONMEN_WORKER_REGION", "")).strip().lower()
        required_tags_raw = request.context.get("worker_tags") or os.getenv("TONMEN_WORKER_TAGS", "")
        if isinstance(required_tags_raw, str):
            required_tags = {item.strip().lower() for item in required_tags_raw.split(",") if item.strip()}
        else:
            required_tags = {str(item).strip().lower() for item in required_tags_raw or () if str(item).strip()}

        candidates = [item for item in self.workers if item.secret_configured]
        if preferred_id:
            candidates = [item for item in candidates if item.id == preferred_id]
        if preferred_region:
            candidates = [item for item in candidates if item.region == preferred_region]
        if required_tags:
            candidates = [item for item in candidates if required_tags.issubset(set(item.tags))]

        def score(item: WorkerSpec) -> tuple[float, int, str]:
            state = self.state[item.id]
            effective = (state.calls + state.failures * 4) / item.weight
            return effective, state.failures, item.id

        return tuple(sorted(candidates, key=score))

    def record_success(self, worker_id: str, health: dict[str, Any] | None = None) -> None:
        state = self.state[normalize_worker_id(worker_id)]
        state.calls += 1
        state.failures = max(0, state.failures - 1)
        state.last_error = None
        if health is not None:
            state.last_health = dict(health)

    def record_failure(self, worker_id: str, error: str) -> None:
        state = self.state[normalize_worker_id(worker_id)]
        state.failures += 1
        state.last_error = str(error)[:300]

    def public_status(self) -> dict[str, Any]:
        return {
            "mode": "worker" if self.workers else "local",
            "strategy": "health-gated weighted least-use",
            "count": len(self.workers),
            "workers": [
                {
                    **item.public_dict(),
                    "calls": self.state[item.id].calls,
                    "failures": self.state[item.id].failures,
                    "last_error": self.state[item.id].last_error,
                    "last_health": self.state[item.id].last_health,
                }
                for item in self.workers
            ],
            "privacy": {
                "secret_values_exposed": False,
                "approval_tokens_sent": False,
                "raw_shell_sent": False,
            },
        }
