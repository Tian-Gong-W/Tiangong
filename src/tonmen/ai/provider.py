from __future__ import annotations

import json
import logging
from typing import Any, Callable, Mapping, Protocol
from urllib.parse import quote
from urllib.request import Request, urlopen

from .config import LeadAIConfig


logger = logging.getLogger(__name__)

JsonRequester = Callable[[str, Mapping[str, str], bytes, int], Mapping[str, Any]]
JsonLoader = Callable[[str, Mapping[str, str], int], Mapping[str, Any]]
JsonValidator = Callable[[Mapping[str, Any]], None]


class LeadAIProvider(Protocol):
    def complete_json(
        self,
        *,
        system: str,
        payload: Mapping[str, Any],
        validator: JsonValidator | None = None,
        max_retries: int = 3,
    ) -> Mapping[str, Any]: ...


def _default_requester(url: str, headers: Mapping[str, str], body: bytes, timeout: int) -> Mapping[str, Any]:
    request = Request(url, data=body, headers=dict(headers), method="POST")
    with urlopen(request, timeout=timeout) as response:  # nosec B310 - URL is validated by LeadAIConfig
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError("Lead AI provider returned a non-object response")
    return payload


def _default_loader(url: str, headers: Mapping[str, str], timeout: int) -> Mapping[str, Any]:
    request = Request(url, headers=dict(headers), method="GET")
    with urlopen(request, timeout=timeout) as response:  # nosec B310 - URL is validated by LeadAIConfig
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError("Lead AI provider returned a non-object response")
    return payload


def _openai_response_text(payload: Mapping[str, Any]) -> str:
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


def _openai_usage(payload: Mapping[str, Any]) -> dict[str, int]:
    raw = payload.get("usage")
    if not isinstance(raw, dict):
        return {}
    result: dict[str, int] = {}
    for key in ("input_tokens", "output_tokens", "total_tokens"):
        value = raw.get(key)
        if isinstance(value, int) and value >= 0:
            result[key] = value
    return result


def _mistral_message_text(payload: Mapping[str, Any]) -> str:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise RuntimeError("Mistral response did not contain choices")
    first = choices[0]
    if not isinstance(first, dict):
        raise RuntimeError("Mistral response choice is invalid")
    message = first.get("message")
    if not isinstance(message, dict):
        raise RuntimeError("Mistral response did not contain a message")
    content = message.get("content")
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
    raise RuntimeError("Mistral response did not contain text output")


def _mistral_usage(payload: Mapping[str, Any]) -> dict[str, int]:
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


def _parse_json_object(text: str) -> Mapping[str, Any]:
    result = json.loads(text)
    if not isinstance(result, dict):
        raise ValueError("Lead AI response JSON must be an object")
    return result


def _validate_max_retries(max_retries: int) -> None:
    if not isinstance(max_retries, int) or isinstance(max_retries, bool) or max_retries < 1:
        raise ValueError("max_retries must be an integer >= 1")


def _merge_usage(total: dict[str, int], current: Mapping[str, int]) -> None:
    for key in ("input_tokens", "output_tokens", "total_tokens"):
        value = current.get(key)
        if isinstance(value, int) and value >= 0:
            total[key] = total.get(key, 0) + value


def _error_summary(exc: BaseException) -> str:
    detail = " ".join(str(exc).split())
    return f"{type(exc).__name__}: {detail}"[:800]


def _correction_message(exc: BaseException) -> str:
    return (
        "SYSTEM INTERCEPT: Your previous output failed validation. "
        f"{_error_summary(exc)}. "
        "Fix it immediately and return ONLY the raw valid JSON matching the required schema and constraints."
    )


class OpenAIResponsesProvider:
    """Tiny server-side Responses API client with an injectable transport for tests."""

    def __init__(self, config: LeadAIConfig, *, requester: JsonRequester = _default_requester) -> None:
        if config.provider != "openai":
            raise ValueError("OpenAIResponsesProvider requires provider='openai'")
        self.config = config
        self._requester = requester
        self.last_usage: dict[str, int] = {}
        self.last_response_id: str | None = None

    def complete_json(
        self,
        *,
        system: str,
        payload: Mapping[str, Any],
        validator: JsonValidator | None = None,
        max_retries: int = 3,
    ) -> Mapping[str, Any]:
        _validate_max_retries(max_retries)
        input_items: list[dict[str, Any]] = [
            {"role": "system", "content": [{"type": "input_text", "text": system}]},
            {
                "role": "user",
                "content": [{"type": "input_text", "text": json.dumps(payload, ensure_ascii=False, separators=(",", ":"))}],
            },
        ]
        cumulative_usage: dict[str, int] = {}
        self.last_usage = {}
        self.last_response_id = None
        last_error: BaseException | None = None

        for attempt in range(1, max_retries + 1):
            request_body = {
                "model": self.config.model,
                "input": input_items,
            }
            raw = self._requester(
                f"{self.config.base_url}/responses",
                {
                    "Authorization": f"Bearer {self.config.api_key()}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "User-Agent": "TONMEN-LeadAI/0.1",
                },
                json.dumps(request_body, ensure_ascii=False).encode("utf-8"),
                self.config.timeout_seconds,
            )
            _merge_usage(cumulative_usage, _openai_usage(raw))
            self.last_usage = dict(cumulative_usage)
            response_id = raw.get("id")
            self.last_response_id = str(response_id)[:120] if response_id else None
            text = _openai_response_text(raw)

            try:
                result = _parse_json_object(text)
                if validator is not None:
                    validator(result)
                return result
            except (json.JSONDecodeError, ValueError) as exc:
                last_error = exc
                if attempt >= max_retries:
                    break
                logger.warning(
                    "SYSTEM INTERCEPT provider=openai attempt=%d/%d validation_failed=%s",
                    attempt,
                    max_retries,
                    _error_summary(exc),
                )
                input_items.extend(
                    [
                        {"role": "assistant", "content": [{"type": "input_text", "text": text}]},
                        {"role": "system", "content": [{"type": "input_text", "text": _correction_message(exc)}]},
                    ]
                )

        raise RuntimeError(
            f"Lead AI failed to produce valid JSON after {max_retries} attempts: {_error_summary(last_error or RuntimeError('validation failed'))}"
        ) from last_error


class MistralAgentProvider:
    """Use a pinned Mistral Studio Agent profile as TONMEN's Lead AI.

    The Agent version is fetched first so TONMEN can reuse its model, instructions,
    and safe completion settings. Agent tools and handoffs are deliberately not
    inherited: all execution authority stays inside TONMEN's governed runtime.
    """

    _SAFE_COMPLETION_ARGS = (
        "temperature",
        "top_p",
        "max_tokens",
        "random_seed",
        "presence_penalty",
        "frequency_penalty",
    )

    def __init__(
        self,
        config: LeadAIConfig,
        *,
        requester: JsonRequester = _default_requester,
        loader: JsonLoader = _default_loader,
    ) -> None:
        if config.provider != "mistral":
            raise ValueError("MistralAgentProvider requires provider='mistral'")
        if not config.agent_id or config.agent_version is None:
            raise ValueError("MistralAgentProvider requires a pinned agent id and version")
        self.config = config
        self._requester = requester
        self._loader = loader
        self._profile: Mapping[str, Any] | None = None
        self.last_usage: dict[str, int] = {}
        self.last_response_id: str | None = None
        self.last_model: str | None = None
        self.last_agent_name: str | None = None

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.config.api_key()}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "TONMEN-LeadAI/0.1",
        }

    def _agent_profile(self) -> Mapping[str, Any]:
        if self._profile is not None:
            return self._profile
        agent_id = quote(str(self.config.agent_id), safe="")
        version = quote(str(self.config.agent_version), safe="")
        profile = self._loader(
            f"{self.config.base_url}/agents/{agent_id}/versions/{version}",
            self._headers(),
            self.config.timeout_seconds,
        )
        model = profile.get("model")
        if not isinstance(model, str) or not model.strip():
            raise RuntimeError("Mistral Agent version did not contain a model")
        self.last_model = model.strip()
        name = profile.get("name")
        self.last_agent_name = str(name)[:160] if name else None
        self._profile = profile
        return profile

    def complete_json(
        self,
        *,
        system: str,
        payload: Mapping[str, Any],
        validator: JsonValidator | None = None,
        max_retries: int = 3,
    ) -> Mapping[str, Any]:
        _validate_max_retries(max_retries)
        profile = self._agent_profile()
        model = str(profile["model"]).strip()
        agent_instructions = str(profile.get("instructions") or "").strip()
        combined_system = (
            f"{agent_instructions}\n\nTONMEN RUNTIME CONSTRAINTS:\n{system}"
            if agent_instructions
            else system
        )

        completion_args: dict[str, Any] = {}
        configured_args = profile.get("completion_args")
        if isinstance(configured_args, dict):
            for key in self._SAFE_COMPLETION_ARGS:
                if key in configured_args:
                    completion_args[key] = configured_args[key]
        completion_args["response_format"] = {"type": "json_object"}

        messages: list[dict[str, str]] = [
            {"role": "system", "content": combined_system},
            {
                "role": "user",
                "content": json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            },
        ]
        cumulative_usage: dict[str, int] = {}
        self.last_usage = {}
        self.last_response_id = None
        last_error: BaseException | None = None

        for attempt in range(1, max_retries + 1):
            request_body = {
                "model": model,
                "messages": messages,
                **completion_args,
            }

            # Intentionally no `tools` or `handoffs`: those belong to Mistral's Agent
            # runtime, while TONMEN's Lead AI is advisory and never receives execution
            # authority outside Scope / Policy / Approval / Executor.
            raw = self._requester(
                f"{self.config.base_url}/chat/completions",
                self._headers(),
                json.dumps(request_body, ensure_ascii=False).encode("utf-8"),
                self.config.timeout_seconds,
            )
            _merge_usage(cumulative_usage, _mistral_usage(raw))
            self.last_usage = dict(cumulative_usage)
            response_id = raw.get("id")
            self.last_response_id = str(response_id)[:120] if response_id else None
            self.last_model = str(raw.get("model") or model)[:160]
            text = _mistral_message_text(raw)

            try:
                result = _parse_json_object(text)
                if validator is not None:
                    validator(result)
                return result
            except (json.JSONDecodeError, ValueError) as exc:
                last_error = exc
                if attempt >= max_retries:
                    break
                logger.warning(
                    "SYSTEM INTERCEPT provider=mistral attempt=%d/%d validation_failed=%s",
                    attempt,
                    max_retries,
                    _error_summary(exc),
                )
                messages.extend(
                    [
                        {"role": "assistant", "content": text},
                        {"role": "user", "content": _correction_message(exc)},
                    ]
                )

        raise RuntimeError(
            f"Lead AI failed to produce valid JSON after {max_retries} attempts: {_error_summary(last_error or RuntimeError('validation failed'))}"
        ) from last_error
