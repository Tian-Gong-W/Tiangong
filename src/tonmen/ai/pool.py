from __future__ import annotations

import os

from .hub import ProviderHub as _ProviderHub

_PROVIDER_IDS = ("openai", "chatgpt", "google", "grok", "deepseek", "mistral")
_ROLES = (
    "surface_mapper",
    "evidence_verifier",
    "vulnerability_analyst",
    "governance_reviewer",
    "remediation_editor",
)


class ProviderHub(_ProviderHub):
    """Explicit provider pool with a side-effect-free public status surface.

    Multi-provider subagent calls require TONMEN_AI_POOL. Merely enabling Lead AI
    never turns on model-backed subagents. Public status intentionally does not run
    browser-login CLI probes; the Console exposes an explicit probe action instead.
    """

    def __init__(self, pool: tuple[str, ...] | None = None) -> None:
        if pool is None:
            values: list[str] = []
            for item in (os.getenv("TONMEN_AI_POOL") or "").split(","):
                provider_id = item.strip().lower()
                if not provider_id or provider_id in values:
                    continue
                try:
                    self.spec(provider_id)
                except ValueError:
                    continue
                values.append(provider_id)
            pool = tuple(values)
        super().__init__(pool=pool)

    def public_status(self) -> dict[str, object]:
        providers: list[dict[str, object]] = []
        for provider_id in _PROVIDER_IDS:
            spec = self.spec(provider_id)
            providers.append(
                {
                    "id": provider_id,
                    "label": spec.label,
                    "transport": spec.transport,
                    "auth_mode": spec.auth_mode,
                    "strength": spec.strength,
                    "cost_weight": spec.cost_weight,
                    "enabled_in_pool": provider_id in self.pool,
                    "installed": self._installed(spec) if spec.executable else None,
                    "executable": spec.executable,
                    "key_env": spec.api_key_env,
                    "key_configured": self._key_configured(spec) if spec.api_key_env else None,
                    "default_model": self.model_for(provider_id),
                    "usage": self.usage[provider_id].as_dict(),
                    "secret_persisted_by_tonmen": False,
                    "secret_exposed_to_browser": False,
                    "probe_is_explicit": True,
                }
            )
        routes = {
            role: (os.getenv(f"TONMEN_AI_ROUTE_{role.upper()}") or "").strip()
            for role in _ROLES
        }
        return {
            "strategy": "weighted_least_usage",
            "pool": list(self.pool),
            "token_budget": self.token_budget,
            "provider_weights": {item: self.weights.get(item, 1.0) for item in self.pool},
            "role_routes": routes,
            "providers": providers,
            "privacy": {
                "credential_values_exposed": False,
                "credential_files_read_by_tonmen": False,
                "raw_evidence_sent": False,
                "approval_tokens_sent": False,
            },
        }
