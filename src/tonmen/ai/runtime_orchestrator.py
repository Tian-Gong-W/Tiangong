from __future__ import annotations

from .chat_provider import ChatCompletionsLeadProvider
from .config import LeadAIConfig
from .orchestrator import LeadAIOrchestrator as BaseLeadAIOrchestrator


class LeadAIOrchestrator(BaseLeadAIOrchestrator):
    """Runtime Lead orchestrator with explicit provider selection.

    The base orchestrator keeps OpenAI Responses and pinned Mistral Agent support.
    This wrapper adds direct DeepSeek and direct Mistral model routes while preserving
    the Lead's advisory-only authority and deterministic failure containment.
    """

    def __init__(self, config: LeadAIConfig | None = None, *, provider=None) -> None:
        resolved = config
        if resolved is None:
            try:
                resolved = LeadAIConfig.from_env()
            except Exception:
                super().__init__(None, provider=provider)
                return

        if provider is None and resolved.enabled:
            if resolved.provider == "deepseek" or (resolved.provider == "mistral" and not resolved.agent_id):
                try:
                    provider = ChatCompletionsLeadProvider(resolved)
                except Exception:
                    provider = None
        super().__init__(resolved, provider=provider)
