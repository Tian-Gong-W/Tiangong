from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import urlparse

from .secrets import get_secret, secret_source
from .settings import get_setting


def _validate_provider_base_url(value: str, provider: str) -> str:
    base_url = value.strip().rstrip("/")
    parsed = urlparse(base_url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https":
        raise ValueError(f"{provider.title()} base URL must use https")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError(f"{provider.title()} base URL may not contain credentials, query, or fragment")
    if provider == "openai":
        if host != "api.openai.com" and not host.endswith(".api.openai.com"):
            raise ValueError("OpenAI base URL must use an official *.api.openai.com host")
    elif provider == "mistral":
        if host != "api.mistral.ai":
            raise ValueError("Mistral base URL must use the official api.mistral.ai host")
    return base_url


def _configured(name: str, fallback: object) -> str:
    raw = os.getenv(name)
    if raw is not None and raw.strip():
        return raw.strip()
    return str(fallback).strip()


def _parse_agent_version(raw: str | None) -> int | str | None:
    value = (raw or "").strip()
    if not value:
        return None
    return int(value) if value.isdigit() else value


@dataclass(frozen=True, slots=True)
class LeadAIConfig:
    """Public configuration for the optional Lead AI.

    Secret values are never stored on this dataclass. Environment variables take
    precedence; the local Console settings/secret stores are fallback sources so a
    local operator can configure AI without restarting or editing shell profiles.

    For Mistral, TONMEN pins a Studio Agent id + version and imports only its model,
    instructions and safe completion settings. Agent tools/handoffs never receive
    TONMEN execution authority.
    """

    provider: str = "disabled"
    model: str = "gpt-5.6"
    base_url: str = "https://api.openai.com/v1"
    api_key_env: str = "OPENAI_API_KEY"
    timeout_seconds: int = 30
    agent_id: str | None = None
    agent_version: int | str | None = None

    @classmethod
    def from_env(cls) -> "LeadAIConfig":
        provider = _configured("TONMEN_AI_PROVIDER", get_setting("lead_provider", "disabled")).lower()
        if provider not in {"disabled", "openai", "mistral"}:
            raise ValueError("TONMEN_AI_PROVIDER must be 'disabled', 'openai', or 'mistral'")

        timeout = int(os.getenv("TONMEN_AI_TIMEOUT_SECONDS") or "30")
        if not 1 <= timeout <= 120:
            raise ValueError("TONMEN_AI_TIMEOUT_SECONDS must be between 1 and 120")

        explicit_key_env = (os.getenv("TONMEN_AI_KEY_ENV") or "").strip()
        default_key_env = "MISTRAL_API_KEY" if provider == "mistral" else "OPENAI_API_KEY"
        key_env = explicit_key_env or default_key_env

        if provider == "mistral":
            base_url = _validate_provider_base_url(
                os.getenv("TONMEN_MISTRAL_BASE_URL") or "https://api.mistral.ai/v1",
                "mistral",
            )
            agent_id = (os.getenv("TONMEN_MISTRAL_AGENT_ID") or "").strip()
            agent_version = _parse_agent_version(os.getenv("TONMEN_MISTRAL_AGENT_VERSION"))
            if not agent_id:
                raise ValueError("TONMEN_MISTRAL_AGENT_ID is required when TONMEN_AI_PROVIDER=mistral")
            if agent_version is None:
                raise ValueError("TONMEN_MISTRAL_AGENT_VERSION is required when TONMEN_AI_PROVIDER=mistral")
            return cls(
                provider="mistral",
                model=f"agent:{agent_id}@{agent_version}",
                base_url=base_url,
                api_key_env=key_env,
                timeout_seconds=timeout,
                agent_id=agent_id,
                agent_version=agent_version,
            )

        base_url = os.getenv("TONMEN_OPENAI_BASE_URL") or "https://api.openai.com/v1"
        if provider == "openai":
            base_url = _validate_provider_base_url(base_url, "openai")
        else:
            base_url = base_url.strip().rstrip("/")
        return cls(
            provider=provider,
            model=_configured("TONMEN_AI_MODEL", get_setting("lead_model", "gpt-5.6")),
            base_url=base_url,
            api_key_env=key_env,
            timeout_seconds=timeout,
        )

    @property
    def enabled(self) -> bool:
        return self.provider != "disabled" and self.key_configured

    @property
    def key_configured(self) -> bool:
        return bool(get_secret(self.api_key_env))

    def api_key(self) -> str:
        value = get_secret(self.api_key_env)
        if not value:
            raise RuntimeError(f"Lead AI key is not configured in {self.api_key_env}")
        return value

    def public_status(self) -> dict[str, object]:
        source = secret_source(self.api_key_env)
        return {
            "enabled": self.enabled,
            "provider": self.provider,
            "model": self.model,
            "base_url": self.base_url,
            "key_env": self.api_key_env,
            "key_configured": self.key_configured,
            "key_source": source,
            "agent_id": self.agent_id,
            "agent_version": self.agent_version,
            "agent_tools_inherited": False,
            "secret_persisted": source == "local_store",
            "secret_exposed": False,
            "raw_evidence_sent": False,
            "execution_authority": False,
        }
