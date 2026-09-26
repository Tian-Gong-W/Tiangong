from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass
class LLMProfile:
    """Database-driven LLM provider configuration.

    Replaces the previously hard-coded per-vendor providers with a generic,
    database-backed profile. ``api_key`` is stored in the database but is never
    serialized to the UI unless explicitly requested.
    """

    id: int | None = None
    name: str = ""
    format: str = "openai"           # "openai" | "openai-responses" | "anthropic"
    base_url: str | None = None
    proxy: str | None = None
    model: str = ""
    api_key: str | None = None       # never serialized to UI by default
    api_key_hint: str | None = None  # "•••" + last 4 chars
    rate_per_second: float = 0.0
    rate_per_minute: float = 0.0
    context_window_k: int = 0
    thinking_type: str | None = None      # "" / "disabled" / "enabled"
    reasoning_effort: str | None = None   # "" / low / medium / high / xhigh / max
    is_default: bool = False              # star = currently active
    priority: int = 0
    pool_exclude: bool = False
    streaming: bool = True
    max_tokens: int = 0
    max_tokens_field: str | None = None   # openai only: "" / "max_completion_tokens"
    session_header_key: str | None = None

    def as_dict(self, *, include_key: bool = False) -> dict[str, Any]:
        data: dict[str, Any] = {
            "id": self.id,
            "name": self.name,
            "format": self.format,
            "base_url": self.base_url,
            "proxy": self.proxy,
            "model": self.model,
            "api_key_hint": self.api_key_hint,
            "rate_per_second": self.rate_per_second,
            "rate_per_minute": self.rate_per_minute,
            "context_window_k": self.context_window_k,
            "thinking_type": self.thinking_type,
            "reasoning_effort": self.reasoning_effort,
            "is_default": self.is_default,
            "priority": self.priority,
            "pool_exclude": self.pool_exclude,
            "streaming": self.streaming,
            "max_tokens": self.max_tokens,
            "max_tokens_field": self.max_tokens_field,
            "session_header_key": self.session_header_key,
        }
        if include_key:
            data["api_key"] = self.api_key
        return data

    @classmethod
    def from_row(cls, row: Mapping[str, Any]) -> "LLMProfile":
        return cls(
            id=row.get("id"),
            name=str(row.get("name") or ""),
            format=str(row.get("format") or "openai"),
            base_url=row.get("base_url"),
            proxy=row.get("proxy"),
            model=str(row.get("model") or ""),
            api_key=row.get("api_key"),
            api_key_hint=row.get("api_key_hint"),
            rate_per_second=float(row.get("rate_per_second") or 0.0),
            rate_per_minute=float(row.get("rate_per_minute") or 0.0),
            context_window_k=int(row.get("context_window_k") or 0),
            thinking_type=row.get("thinking_type"),
            reasoning_effort=row.get("reasoning_effort"),
            is_default=bool(row.get("is_default")),
            priority=int(row.get("priority") or 0),
            pool_exclude=bool(row.get("pool_exclude")),
            streaming=bool(row.get("streaming", True)),
            max_tokens=int(row.get("max_tokens") or 0),
            max_tokens_field=row.get("max_tokens_field"),
            session_header_key=row.get("session_header_key"),
        )
