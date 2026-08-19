from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import urlparse


def _validate_openai_base_url(value: str) -> str:
    base_url = value.strip().rstrip("/")
    parsed = urlparse(base_url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https":
        raise ValueError("OpenAI base URL must use https")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("OpenAI base URL may not contain credentials, query, or fragment")
    if host != "api.openai.com" and not host.endswith(".api.openai.com"):
        raise ValueError("OpenAI base URL must use an official *.api.openai.com host")
    return base_url


@dataclass(frozen=True, slots=True)
class LeadAIConfig:
    """Public configuration for the optional Lead AI.

    The API key is intentionally never stored on this object. Providers read the
    configured secret environment variable only at request time so the key cannot
    accidentally flow into dataclasses, reports, Chronicle, Events, or UI payloads.
    """

    provider: str = "disabled"
    model: str = "gpt-5.6"
    base_url: str = "https://api.openai.com/v1"
    api_key_env: str = "OPENAI_API_KEY"
    timeout_seconds: int = 30

    @classmethod
    def from_env(cls) -> "LeadAIConfig":
        key_env = (os.getenv("TONMEN_AI_KEY_ENV") or "OPENAI_API_KEY").strip()
        # Explicit opt-in avoids surprise network calls/cost merely because a shell
        # already contains an unrelated OPENAI_API_KEY.
        provider = (os.getenv("TONMEN_AI_PROVIDER") or "disabled").strip().lower()
        if provider not in {"disabled", "openai"}:
            raise ValueError("TONMEN_AI_PROVIDER must be 'disabled' or 'openai'")
        timeout = int(os.getenv("TONMEN_AI_TIMEOUT_SECONDS") or "30")
        if not 1 <= timeout <= 120:
            raise ValueError("TONMEN_AI_TIMEOUT_SECONDS must be between 1 and 120")
        base_url = (os.getenv("TONMEN_OPENAI_BASE_URL") or "https://api.openai.com/v1").strip().rstrip("/")
        if provider == "openai":
            base_url = _validate_openai_base_url(base_url)
        return cls(
            provider=provider,
            model=(os.getenv("TONMEN_AI_MODEL") or "gpt-5.6").strip(),
            base_url=base_url,
            api_key_env=key_env,
            timeout_seconds=timeout,
        )

    @property
    def enabled(self) -> bool:
        return self.provider != "disabled" and self.key_configured

    @property
    def key_configured(self) -> bool:
        return bool(os.getenv(self.api_key_env, "").strip())

    def api_key(self) -> str:
        value = os.getenv(self.api_key_env, "").strip()
        if not value:
            raise RuntimeError(f"Lead AI key is not configured in {self.api_key_env}")
        return value

    def public_status(self) -> dict[str, object]:
        return {
            "enabled": self.enabled,
            "provider": self.provider,
            "model": self.model,
            "base_url": self.base_url,
            "key_env": self.api_key_env,
            "key_configured": self.key_configured,
            "secret_persisted": False,
            "raw_evidence_sent": False,
            "execution_authority": False,
        }
