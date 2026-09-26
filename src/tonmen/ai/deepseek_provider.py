from __future__ import annotations

from typing import Any, Mapping

from .config import LeadAIConfig
from .hub import ProviderHub as RawProviderHub


class DeepSeekChatProvider:
    """Evidence-only DeepSeek provider for the Lead AI path.

    Reuses the existing ProviderHub chat-completions transport so Lead and Council
    share the same response parsing semantics. No tool or execution authority is
    delegated to the remote model.
    """

    def __init__(self, config: LeadAIConfig) -> None:
        if config.provider != "deepseek":
            raise ValueError("DeepSeekChatProvider requires provider='deepseek'")
        self.config = config
        self.last_usage: dict[str, int] = {}
        self.last_response_id: str | None = None
        self.last_model: str | None = config.model

    def complete_json(self, *, system: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        # LeadAIConfig may resolve a locally persisted secret. ProviderHub reads
        # the hydrated environment copy populated by apply_local_ai_environment().
        hub = RawProviderHub(pool=("deepseek",))
        result, usage, _estimated = hub.complete_json(
            "deepseek",
            self.config.model,
            system=system,
            payload=payload,
        )
        self.last_usage = dict(usage)
        self.last_model = self.config.model
        return result
