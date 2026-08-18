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
