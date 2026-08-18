from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import urlparse


_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


@dataclass(frozen=True, slots=True)
class ModelRuntimeConfig:
    """Optional model runtime configuration.

    `none` keeps TONMEN fully deterministic. `ollama` connects only to a loopback
    Ollama server and therefore requires no cloud API key.
    """

    provider: str = "none"
    model: str = ""
    base_url: str = "http://127.0.0.1:11434/api"
    timeout_seconds: int = 60
    max_calls: int = 50

    def __post_init__(self) -> None:
        provider = self.provider.strip().lower()
        if provider not in {"none", "ollama"}:
            raise ValueError("model provider must be 'none' or 'ollama'")
        if not 1 <= int(self.timeout_seconds) <= 300:
            raise ValueError("model timeout_seconds must be between 1 and 300")
        if not 1 <= int(self.max_calls) <= 50:
            raise ValueError("model max_calls must be between 1 and 50")
        if provider == "ollama":
            if not self.model.strip():
                raise ValueError("ollama model name is required")
            parsed = urlparse(self.base_url)
            if parsed.scheme != "http" or parsed.hostname not in _LOCAL_HOSTS:
                raise ValueError("ollama base_url must use loopback HTTP only")
            if parsed.username or parsed.password or parsed.query or parsed.fragment:
                raise ValueError("ollama base_url must not contain credentials, query or fragment")

    @property
    def enabled(self) -> bool:
        return self.provider.strip().lower() != "none"

    @classmethod
    def from_environment(cls) -> "ModelRuntimeConfig":
        provider = os.getenv("TONMEN_MODEL_PROVIDER", "none").strip().lower()
        if provider == "none":
            return cls()
        return cls(
            provider=provider,
            model=os.getenv("TONMEN_MODEL_NAME", "").strip(),
            base_url=os.getenv("TONMEN_MODEL_BASE_URL", "http://127.0.0.1:11434/api").strip(),
            timeout_seconds=int(os.getenv("TONMEN_MODEL_TIMEOUT", "60")),
            max_calls=int(os.getenv("TONMEN_MODEL_MAX_CALLS", "50")),
        )
