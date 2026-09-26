from __future__ import annotations

from typing import Any, Mapping

from .config import LeadAIConfig
from .hub import ProviderHub as RawProviderHub


class ChatCompletionsLeadProvider:
    """Direct evidence-only Lead adapter for ProviderHub chat-completions APIs."""

    def __init__(self, config: LeadAIConfig) -> None:
        if config.provider not in {"deepseek", "mistral"}:
            raise ValueError("ChatCompletionsLeadProvider requires deepseek or mistral")
        if config.provider == "mistral" and config.agent_id:
            raise ValueError("pinned Mistral Agents use MistralAgentProvider")
        self.config = config
        self.last_usage: dict[str, int] = {}
        self.last_response_id: str | None = None
        self.last_model: str | None = config.model

    def complete_json(self, *, system: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        hub = RawProviderHub(pool=(self.config.provider,))
        result, usage, _estimated = hub.complete_json(
            self.config.provider,
            self.config.model,
            system=system,
            payload=payload,
        )
        self.last_usage = dict(usage)
        self.last_model = self.config.model
        return result
