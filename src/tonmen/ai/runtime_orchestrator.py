from __future__ import annotations

from .config import LeadAIConfig
from .deepseek_provider import DeepSeekChatProvider
from .orchestrator import LeadAIOrchestrator as BaseLeadAIOrchestrator


class LeadAIOrchestrator(BaseLeadAIOrchestrator):
    """Runtime Lead orchestrator with explicit provider selection.

    The legacy orchestrator already supports OpenAI and pinned Mistral Agents. This
    wrapper adds DeepSeek without changing the Lead's advisory-only authority model.
    """

    def __init__(self, config: LeadAIConfig | None = None, *, provider=None) -> None:
        resolved = config
        if resolved is None:
            try:
                resolved = LeadAIConfig.from_env()
            except Exception:
                # Preserve the base orchestrator's existing failure-contained config
                # behavior and deterministic fallback diagnostics.
                super().__init__(None, provider=provider)
                return

        if provider is None and resolved.enabled and resolved.provider == "deepseek":
            try:
                provider = DeepSeekChatProvider(resolved)
            except Exception:
                # Let the base class expose configuration/provider errors using its
                # deterministic fallback rather than failing the Mission runtime.
                provider = None
        super().__init__(resolved, provider=provider)
