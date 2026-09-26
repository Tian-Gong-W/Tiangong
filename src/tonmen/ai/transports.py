from __future__ import annotations

import json
import threading
import time
from abc import ABC, abstractmethod
from typing import Any, Mapping
from urllib.request import Request, urlopen

try:  # profiles.py is implemented by a sibling agent; do not hard-depend on it.
    from .profiles import LLMProfile  # type: ignore[attr-defined]
except Exception:  # pragma: no cover - profiles.py may not exist yet
    from typing import Protocol

    class LLMProfile(Protocol):  # type: ignore[no-redef]
        """Loose structural type standing in for profiles.LLMProfile.

        Only the fields listed here are read by the transports: ``format``,
        ``model``, ``base_url``, ``api_key``, ``rate_per_second``,
        ``rate_per_minute``, ``proxy``, ``streaming``, ``max_tokens``,
        ``max_tokens_field``, ``thinking_type``, ``reasoning_effort`` and
        ``context_window_k``.
        """

        format: str
        model: str
        base_url: str
        api_key: str
        rate_per_second: float
        rate_per_minute: float
        proxy: Any
        streaming: bool
        max_tokens: int
        max_tokens_field: str
        thinking_type: str
        reasoning_effort: str
        context_window_k: int

        @property
        def id(self) -> Any: ...
        @property
        def name(self) -> str: ...


DEFAULT_TIMEOUT_SECONDS = 45
DEFAULT_MAX_TOKENS = 4096


class RateLimiter:
    """Process-local token-bucket rate limiter keyed per profile.

    A single profile (identified by its ``id`` or ``name``) shares one limiter
    across all transports via a class-level dict. ``rate_per_second`` and
    ``rate_per_minute`` are independent ceilings; when both are zero the
    ``acquire`` call returns immediately.
    """

    _instances: dict[Any, "RateLimiter"] = {}
    _lock = threading.Lock()

    def __init__(self, per_second: float, per_minute: float) -> None:
        self._per_second = float(per_second or 0)
        self._per_minute = float(per_minute or 0)
        self._last = 0.0
        self._guard = threading.Lock()

    @classmethod
    def for_profile(cls, profile: Any) -> "RateLimiter":
        key = getattr(profile, "id", None) or getattr(profile, "name", None) or id(profile)
        with cls._lock:
            limiter = cls._instances.get(key)
            if limiter is None:
                limiter = cls(
                    getattr(profile, "rate_per_second", 0) or 0,
                    getattr(profile, "rate_per_minute", 0) or 0,
                )
                cls._instances[key] = limiter
            return limiter

    def acquire(self) -> None:
        """Block until a call is allowed under both rate ceilings."""
        if self._per_second <= 0 and self._per_minute <= 0:
            return
        with self._guard:
            now = time.monotonic()
            elapsed = now - self._last
            # Each ceiling implies a minimum interval since the last call.
            intervals: list[float] = []
            if self._per_second > 0:
                intervals.append(1.0 / self._per_second)
            if self._per_minute > 0:
                intervals.append(60.0 / self._per_minute)
            required = max(intervals)
            wait = max(0.0, required - elapsed)
            if wait > 0:
                time.sleep(wait)
            self._last = time.monotonic()


def _extract_json_text(text: str) -> str:
    """Return the text directly if it is a JSON document, else the first {...} substring."""
    stripped = text.strip()
    if not stripped:
        return stripped
    start = stripped.find("{")
    if start >= 0:
        stripped = stripped[start:]
        end = stripped.rfind("}")
        if end >= 0:
            stripped = stripped[: end + 1]
    return stripped


def _parse_json_object(text: str) -> Mapping[str, Any]:
    """Parse provider text into a JSON object or raise RuntimeError."""
    cleaned = _extract_json_text(text)
    if not cleaned:
        raise RuntimeError("AI response was empty")
    try:
        result = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise RuntimeError("AI response was not valid JSON") from exc
    if not isinstance(result, dict):
        raise RuntimeError("AI response JSON must be an object")
    return result


def _openai_choice_text(payload: Mapping[str, Any]) -> str:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise RuntimeError("OpenAI response did not contain choices")
    first = choices[0]
    if not isinstance(first, dict):
        raise RuntimeError("OpenAI response choice is invalid")
    message = first.get("message")
    if not isinstance(message, dict):
        raise RuntimeError("OpenAI response did not contain a message")
    content = message.get("content")
    if isinstance(content, str) and content.strip():
        return content.strip()
    raise RuntimeError("OpenAI response did not contain text output")


def _openai_chat_usage(payload: Mapping[str, Any]) -> dict[str, int]:
    raw = payload.get("usage")
    if not isinstance(raw, dict):
        return {}
    result: dict[str, int] = {}
    prompt = raw.get("prompt_tokens")
    completion = raw.get("completion_tokens")
    total = raw.get("total_tokens")
    if isinstance(prompt, int) and prompt >= 0:
        result["input_tokens"] = prompt
    if isinstance(completion, int) and completion >= 0:
        result["output_tokens"] = completion
    if isinstance(total, int) and total >= 0:
        result["total_tokens"] = total
    return result


def _openai_responses_text(payload: Mapping[str, Any]) -> str:
    direct = payload.get("output_text")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()
    output = payload.get("output")
    if not isinstance(output, list):
        raise RuntimeError("OpenAI response did not contain output")
    for item in output:
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        content = item.get("content")
        if not isinstance(content, list):
            continue
        for part in content:
            if isinstance(part, dict) and part.get("type") == "output_text" and isinstance(part.get("text"), str):
                return part["text"].strip()
    raise RuntimeError("OpenAI response did not contain output text")


def _openai_responses_usage(payload: Mapping[str, Any]) -> dict[str, int]:
    raw = payload.get("usage")
    if not isinstance(raw, dict):
        return {}
    result: dict[str, int] = {}
    for key in ("input_tokens", "output_tokens", "total_tokens"):
        value = raw.get(key)
        if isinstance(value, int) and value >= 0:
            result[key] = value
    return result


def _anthropic_text(payload: Mapping[str, Any]) -> str:
    content = payload.get("content")
    if isinstance(content, str) and content.strip():
        return content.strip()
    if isinstance(content, list):
        chunks: list[str] = []
        for part in content:
            if not isinstance(part, dict):
                continue
            if part.get("type") == "text" and isinstance(part.get("text"), str):
                chunks.append(part["text"])
        text = "".join(chunks).strip()
        if text:
            return text
        if len(content) == 1 and isinstance(content[0], dict) and "text" in content[0]:
            value = content[0].get("text")
            if isinstance(value, str) and value.strip():
                return value.strip()
    raise RuntimeError("Anthropic response did not contain text output")


def _anthropic_usage(payload: Mapping[str, Any]) -> dict[str, int]:
    raw = payload.get("usage")
    if not isinstance(raw, dict):
        return {}
    input_tokens = raw.get("input_tokens")
    output_tokens = raw.get("output_tokens")
    result: dict[str, int] = {}
    if isinstance(input_tokens, int) and input_tokens >= 0:
        result["input_tokens"] = input_tokens
    if isinstance(output_tokens, int) and output_tokens >= 0:
        result["output_tokens"] = output_tokens
    if "input_tokens" in result or "output_tokens" in result:
        result["total_tokens"] = result.get("input_tokens", 0) + result.get("output_tokens", 0)
    return result


class Transport(ABC):
    """Protocol adapter for a single AI provider wire format.

    Subclasses only need to implement the HTTP request shape and response
    parsing; rate limiting, JSON extraction and timeout handling are shared.
    """

    format: str

    @abstractmethod
    def complete_json(
        self,
        profile: Any,
        *,
        system: str,
        payload: Mapping[str, Any],
    ) -> tuple[Mapping[str, Any], dict[str, int], bool]:
        """Return ``(parsed_json_dict, usage_dict, estimated_bool)``.

        ``usage_dict`` uses the fixed keys ``input_tokens`` / ``output_tokens`` /
        ``total_tokens``.
        """

    @abstractmethod
    def probe(self, profile: Any, *, timeout: int = 8) -> dict[str, Any]:
        """Return ``{"ready": bool, "detail": str}``."""

    def _timeout(self, profile: Any) -> int:
        value = getattr(profile, "timeout_seconds", None)
        if isinstance(value, int) and value > 0:
            return value
        return DEFAULT_TIMEOUT_SECONDS

    def _rate_limiter(self, profile: Any) -> RateLimiter:
        return RateLimiter.for_profile(profile)

    def _post(self, url: str, headers: Mapping[str, str], body: Mapping[str, Any], timeout: int) -> Mapping[str, Any]:
        request = Request(url, data=json.dumps(body, ensure_ascii=False).encode("utf-8"), headers=dict(headers), method="POST")
        with urlopen(request, timeout=timeout) as response:  # nosec B310 - URL comes from stored profile config
            result = json.loads(response.read().decode("utf-8"))
        if not isinstance(result, dict):
            raise RuntimeError("AI provider returned a non-object response")
        return result


class OpenAITransport(Transport):
    """OpenAI chat completions adapter (/chat/completions)."""

    format = "openai"

    def complete_json(
        self,
        profile: Any,
        *,
        system: str,
        payload: Mapping[str, Any],
    ) -> tuple[Mapping[str, Any], dict[str, int], bool]:
        self._rate_limiter(profile).acquire()
        body = {
            "model": profile.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False, separators=(",", ":"))},
            ],
            "response_format": {"type": "json_object"},
        }
        raw = self._post(
            f"{str(profile.base_url).rstrip('/')}/chat/completions",
            {
                "Authorization": f"Bearer {profile.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "TONMEN-Transport/0.1",
            },
            body,
            self._timeout(profile),
        )
        usage = _openai_chat_usage(raw)
        return _parse_json_object(_openai_choice_text(raw)), usage, False

    def probe(self, profile: Any, *, timeout: int = 8) -> dict[str, Any]:
        if profile.api_key:
            return {"ready": True, "detail": "api key configured"}
        return {"ready": False, "detail": "api key missing"}


class OpenAIResponsesTransport(Transport):
    """OpenAI Responses API adapter (/responses)."""

    format = "openai-responses"

    def complete_json(
        self,
        profile: Any,
        *,
        system: str,
        payload: Mapping[str, Any],
    ) -> tuple[Mapping[str, Any], dict[str, int], bool]:
        self._rate_limiter(profile).acquire()
        body = {
            "model": profile.model,
            "input": [
                {"role": "system", "content": [{"type": "input_text", "text": system}]},
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": json.dumps(payload, ensure_ascii=False, separators=(",", ":"))}],
                },
            ],
        }
        raw = self._post(
            f"{str(profile.base_url).rstrip('/')}/responses",
            {
                "Authorization": f"Bearer {profile.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "TONMEN-Transport/0.1",
            },
            body,
            self._timeout(profile),
        )
        usage = _openai_responses_usage(raw)
        return _parse_json_object(_openai_responses_text(raw)), usage, False

    def probe(self, profile: Any, *, timeout: int = 8) -> dict[str, Any]:
        if profile.api_key:
            return {"ready": True, "detail": "api key configured"}
        return {"ready": False, "detail": "api key missing"}


class AnthropicTransport(Transport):
    """Anthropic Messages API adapter (/v1/messages)."""

    format = "anthropic"

    def complete_json(
        self,
        profile: Any,
        *,
        system: str,
        payload: Mapping[str, Any],
    ) -> tuple[Mapping[str, Any], dict[str, int], bool]:
        self._rate_limiter(profile).acquire()
        max_tokens = profile.max_tokens or DEFAULT_MAX_TOKENS
        body = {
            "model": profile.model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": [
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False, separators=(",", ":"))},
            ],
        }
        raw = self._post(
            f"{str(profile.base_url).rstrip('/')}/v1/messages",
            {
                "x-api-key": profile.api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "TONMEN-Transport/0.1",
            },
            body,
            self._timeout(profile),
        )
        usage = _anthropic_usage(raw)
        return _parse_json_object(_anthropic_text(raw)), usage, False

    def probe(self, profile: Any, *, timeout: int = 8) -> dict[str, Any]:
        if profile.api_key:
            return {"ready": True, "detail": "api key configured"}
        return {"ready": False, "detail": "api key missing"}


TRANSPORT_REGISTRY: dict[str, Transport] = {
    t.format: t for t in (OpenAITransport(), OpenAIResponsesTransport(), AnthropicTransport())
}
