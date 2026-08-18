from __future__ import annotations

import ipaddress
import json
import socket
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import ProxyHandler, Request, build_opener

from tonmen.core.config import validate_local_ai_base_url

from .model import AIAdvisory, AIHypothesis, AIProviderError, AIProviderStatus

_MAX_RESPONSE_BYTES = 2 * 1024 * 1024

_ADVISORY_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "summary": {"type": "string"},
        "focus": {"type": "array", "items": {"type": "string"}, "maxItems": 8},
        "hypotheses": {
            "type": "array",
            "maxItems": 8,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "key": {"type": "string"},
                    "summary": {"type": "string"},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "basis_fact_ids": {"type": "array", "items": {"type": "string"}, "maxItems": 16},
                },
                "required": ["key", "summary", "confidence", "basis_fact_ids"],
            },
        },
        "challenge_decision": {"type": "boolean"},
        "challenge_reason": {"type": "string"},
        "basis_fact_ids": {"type": "array", "items": {"type": "string"}, "maxItems": 16},
    },
    "required": ["summary", "focus", "hypotheses", "challenge_decision", "challenge_reason", "basis_fact_ids"],
}

_SYSTEM_PROMPT = """You are TONMEN's local evidence-analysis advisor.
You have NO execution authority. Evaluate only the supplied target profile, evidence facts,
confidence/conflict posture and deterministic decision. Do not create shell commands, raw
argv, payloads, credentials, session-takeover steps, persistence, scope expansion or approval.
Return only the requested structured JSON. Keep claims tied to supplied fact IDs. A missing
fact is uncertainty, not contradictory evidence. If you challenge the deterministic decision,
explain the evidence conflict or analytical gap; do not propose an unauthorized action."""


def _clean_text(value: Any, *, limit: int) -> str:
    text = str(value or "").strip()
    return text[:limit]


class OllamaProvider:
    """No-key Ollama provider restricted to a loopback HTTP origin."""

    name = "ollama"

    def __init__(self, *, base_url: str, model: str, timeout_seconds: int = 20) -> None:
        self.base_url = validate_local_ai_base_url(base_url)
        self.model = str(model).strip()
        if not self.model:
            raise ValueError("Ollama model is required")
        self.timeout_seconds = int(timeout_seconds)
        if not 1 <= self.timeout_seconds <= 120:
            raise ValueError("Ollama timeout must be between 1 and 120 seconds")
        self._opener = build_opener(ProxyHandler({}))

    def _assert_resolves_loopback(self) -> None:
        parsed = urlparse(self.base_url)
        host = parsed.hostname or ""
        port = parsed.port or 80
        try:
            addresses = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        except OSError as exc:
            raise AIProviderError(f"local AI hostname resolution failed: {exc}") from exc
        if not addresses:
            raise AIProviderError("local AI hostname did not resolve")
        for item in addresses:
            address = item[4][0]
            try:
                if not ipaddress.ip_address(address).is_loopback:
                    raise AIProviderError("local AI hostname resolved outside loopback")
            except ValueError as exc:
                raise AIProviderError("local AI resolved to an invalid address") from exc

    def _request_json(self, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        self._assert_resolves_loopback()
        url = f"{self.base_url}{path}"
        data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = Request(
            url,
            data=data,
            method="GET" if payload is None else "POST",
            headers={"Accept": "application/json", "Content-Type": "application/json"},
        )
        try:
            with self._opener.open(request, timeout=self.timeout_seconds) as response:
                raw = response.read(_MAX_RESPONSE_BYTES + 1)
        except HTTPError as exc:
            raise AIProviderError(f"Ollama HTTP {exc.code}") from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise AIProviderError(f"Ollama unavailable: {exc}") from exc
        if len(raw) > _MAX_RESPONSE_BYTES:
            raise AIProviderError("Ollama response exceeded 2 MiB")
        try:
            result = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AIProviderError("Ollama returned invalid JSON") from exc
        if not isinstance(result, dict):
            raise AIProviderError("Ollama response must be a JSON object")
        return result

    def status(self) -> AIProviderStatus:
        try:
            data = self._request_json("/api/tags")
        except AIProviderError as exc:
            return AIProviderStatus(
                enabled=True,
                provider=self.name,
                model=self.model,
                ready=False,
                code="provider_unavailable",
                detail=str(exc),
            )
        models = data.get("models", [])
        names: set[str] = set()
        if isinstance(models, list):
            for item in models:
                if not isinstance(item, dict):
                    continue
                for key in ("name", "model"):
                    value = item.get(key)
                    if isinstance(value, str) and value.strip():
                        names.add(value.strip())
        if self.model not in names:
            return AIProviderStatus(
                enabled=True,
                provider=self.name,
                model=self.model,
                ready=False,
                code="model_missing",
                detail=f"local Ollama model is not installed: {self.model}",
            )
        return AIProviderStatus(
            enabled=True,
            provider=self.name,
            model=self.model,
            ready=True,
            code="ready",
            detail=f"local Ollama model ready: {self.model}",
        )

    def advise(self, context: dict[str, Any], *, allowed_fact_ids: set[str]) -> AIAdvisory:
        prompt = (
            "Review this governed assessment snapshot. Return structured evidence analysis only.\n\n"
            + json.dumps(context, ensure_ascii=False, sort_keys=True)
        )
        response = self._request_json(
            "/api/chat",
            {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                "stream": False,
                "format": _ADVISORY_SCHEMA,
                "options": {"temperature": 0},
            },
        )
        message = response.get("message")
        if not isinstance(message, dict) or not isinstance(message.get("content"), str):
            raise AIProviderError("Ollama chat response did not contain message.content")
        try:
            payload = json.loads(message["content"])
        except json.JSONDecodeError as exc:
            raise AIProviderError("Ollama advisory content was not valid JSON") from exc
        if not isinstance(payload, dict):
            raise AIProviderError("Ollama advisory must be a JSON object")

        def fact_ids(values: Any) -> tuple[str, ...]:
            if not isinstance(values, list):
                return ()
            return tuple(dict.fromkeys(str(item) for item in values if str(item) in allowed_fact_ids))[:16]

        hypotheses: list[AIHypothesis] = []
        raw_hypotheses = payload.get("hypotheses", [])
        if isinstance(raw_hypotheses, list):
            for item in raw_hypotheses[:8]:
                if not isinstance(item, dict):
                    continue
                try:
                    confidence = float(item.get("confidence", 0.0))
                except (TypeError, ValueError):
                    confidence = 0.0
                hypotheses.append(
                    AIHypothesis(
                        key=_clean_text(item.get("key"), limit=96),
                        summary=_clean_text(item.get("summary"), limit=600),
                        confidence=max(0.0, min(1.0, confidence)),
                        basis_fact_ids=fact_ids(item.get("basis_fact_ids")),
                    )
                )

        raw_focus = payload.get("focus", [])
        focus = tuple(
            _clean_text(item, limit=160)
            for item in (raw_focus[:8] if isinstance(raw_focus, list) else [])
            if _clean_text(item, limit=160)
        )
        basis = fact_ids(payload.get("basis_fact_ids"))
        for item in hypotheses:
            basis += tuple(fact_id for fact_id in item.basis_fact_ids if fact_id not in basis)
        basis = basis[:16]

        return AIAdvisory(
            provider=self.name,
            model=self.model,
            summary=_clean_text(payload.get("summary"), limit=1600),
            focus=focus,
            hypotheses=tuple(hypotheses),
            challenge_decision=bool(payload.get("challenge_decision", False)),
            challenge_reason=_clean_text(payload.get("challenge_reason"), limit=1000),
            basis_fact_ids=basis,
            execution_authority=False,
            local_only=True,
        )
