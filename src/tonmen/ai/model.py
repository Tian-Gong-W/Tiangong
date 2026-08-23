from __future__ import annotations

from dataclasses import dataclass


class AIProviderError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class AIProviderStatus:
    enabled: bool
    provider: str
    model: str
    ready: bool
    code: str
    detail: str
    local_only: bool = True
    api_key_required: bool = False


@dataclass(frozen=True, slots=True)
class AIHypothesis:
    key: str
    summary: str
    confidence: float
    basis_fact_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class AICapabilityPreference:
    """Read-only preference over a catalog candidate already supplied by TONMEN."""

    tool: str
    preference: float
    rationale: str
    basis_fact_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not -1.0 <= float(self.preference) <= 1.0:
            raise ValueError("AI capability preference must be between -1 and 1")


@dataclass(frozen=True, slots=True)
class AIAdvisory:
    provider: str
    model: str
    summary: str
    focus: tuple[str, ...]
    hypotheses: tuple[AIHypothesis, ...]
    challenge_decision: bool
    challenge_reason: str
    basis_fact_ids: tuple[str, ...]
    execution_authority: bool = False
    local_only: bool = True
    capability_preferences: tuple[AICapabilityPreference, ...] = ()
