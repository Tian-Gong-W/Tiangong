from __future__ import annotations

import os
from typing import Any

from tonmen.ai import ProviderHub
from tonmen.ai.auth_broker import ProviderAuthBroker
from tonmen.ai.settings import public_settings, update_settings

from .mission_workspace_server import DashboardState as MissionWorkspaceDashboardState


_LEAD_PROVIDER_IDS = ("openai", "deepseek", "mistral")


class DashboardState(MissionWorkspaceDashboardState):
    """Production dashboard state with durable-provider auth semantics."""

    def __init__(self, config) -> None:
        super().__init__(config)
        self._provider_auth_broker = ProviderAuthBroker()

    def provider_hub(self) -> dict[str, Any]:
        payload = super().provider_hub()
        hub = ProviderHub()
        providers = []
        provider_by_id: dict[str, dict[str, Any]] = {}
        for provider in payload.get("providers", []):
            if not isinstance(provider, dict):
                continue
            item = dict(provider)
            provider_id = str(item.get("id") or "").strip().lower()
            if not provider_id:
                continue
            try:
                runtime = hub.authentication_status(provider_id, timeout=2)
            except Exception as exc:
                runtime = {
                    "authenticated": False,
                    "runtime_ready": False,
                    "runtime_blocker": str(exc)[:300],
                    "ready": False,
                }
            item["authenticated"] = bool(runtime.get("authenticated"))
            item["runtime_ready"] = bool(runtime.get("runtime_ready"))
            item["runtime_blocker"] = runtime.get("runtime_blocker")
            item["auth_session"] = self._provider_auth_broker.status(provider_id)
            providers.append(item)
            provider_by_id[provider_id] = item
        payload["providers"] = providers
        payload["lead_provider_options"] = [
            {
                "id": "disabled",
                "label": "Disabled",
                "default_model": None,
                "configured": True,
            },
            *[
                {
                    "id": provider_id,
                    "label": str(provider_by_id.get(provider_id, {}).get("label") or provider_id),
                    "default_model": provider_by_id.get(provider_id, {}).get("default_model"),
                    "configured": bool(
                        provider_by_id.get(provider_id, {}).get("key_configured")
                        or provider_by_id.get(provider_id, {}).get("local_secret", {}).get("configured")
                    ),
                }
                for provider_id in _LEAD_PROVIDER_IDS
            ],
        ]
        payload["provider_home"] = os.getenv("HOME", "")
        payload["credential_values_exposed"] = False
        return payload

    def launch_provider_login(self, provider_id: str) -> dict[str, Any]:
        result = self._provider_auth_broker.start(provider_id)
        self.events.publish(
            "ai.provider_login_started",
            provider=provider_id,
            auth_mode="browser_login",
            credential_values_exposed=False,
        )
        return result

    def probe_provider(self, provider_id: str) -> dict[str, Any]:
        hub = ProviderHub()
        ProviderHub.invalidate_probe(provider_id)
        raw = hub.probe(provider_id, timeout=8)
        result = {
            "provider": provider_id,
            "ready": bool(raw.get("runtime_ready")),
            "authenticated": bool(raw.get("authenticated")),
            "runtime_ready": bool(raw.get("runtime_ready")),
            "runtime_blocker": raw.get("runtime_blocker"),
            "installed": raw.get("installed"),
            "detail": str(raw.get("detail") or "")[:500],
            "auth_mode": raw.get("auth_mode") or hub.spec(provider_id).auth_mode,
            "credential_values_exposed": False,
        }
        self._provider_probes[provider_id] = result
        self.events.publish(
            "ai.provider_probed",
            provider=provider_id,
            ready=result["ready"],
            authenticated=result["authenticated"],
            auth_mode=result["auth_mode"],
        )
        return result

    def update_ai_configuration(self, data: dict[str, Any]) -> dict[str, Any]:
        lead_enabled = data.get("lead_enabled") if "lead_enabled" in data else None
        lead_provider = data.get("lead_provider") if "lead_provider" in data else None
        lead_model = data.get("lead_model") if "lead_model" in data else None
        pool = data.get("pool") if "pool" in data else None
        if pool is not None and not isinstance(pool, list):
            raise ValueError("pool must be a list")

        current = public_settings()
        provider = str(lead_provider if lead_provider is not None else current.get("lead_provider") or "disabled").strip().lower()
        if lead_enabled is False:
            provider = "disabled"
        elif lead_enabled is True and provider == "disabled":
            provider = "openai"

        stored = update_settings(
            lead_provider=provider,
            lead_model=lead_model,
            pool=pool,
        )
        if "TONMEN_AI_PROVIDER" not in self._explicit_ai_env:
            os.environ["TONMEN_AI_PROVIDER"] = provider
        if lead_model is not None and "TONMEN_AI_MODEL" not in self._explicit_ai_env:
            os.environ["TONMEN_AI_MODEL"] = str(lead_model).strip()
        if pool is not None and "TONMEN_AI_POOL" not in self._explicit_ai_env:
            os.environ["TONMEN_AI_POOL"] = ",".join(str(item).strip().lower() for item in pool if str(item).strip())

        ProviderHub.invalidate_probe()
        self.events.publish(
            "ai.local_settings_updated",
            lead_provider=provider,
            secret_exposed=False,
        )
        return {
            "settings": stored,
            "environment_overrides": sorted(self._explicit_ai_env),
            "applied_without_restart": True,
            "secret_exposed": False,
        }
