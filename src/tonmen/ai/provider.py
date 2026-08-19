from __future__ import annotations

import json
from typing import Any, Callable, Mapping
from urllib.request import Request, urlopen

from .config import LeadAIConfig


JsonRequester = Callable[[str, Mapping[str, str], bytes, int], Mapping[str, Any]]


def _default_requester(url: str, headers: Mapping[str, str], body: bytes, timeout: int) -> Mapping[str, Any]:
    request = Request(url, data=body, headers=dict(headers), method="POST")
    with urlopen(request, timeout=timeout) as response:  # nosec B310 - URL is validated by LeadAIConfig
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError("Lead AI provider returned a non-object response")
    return payload


def _response_text(payload: Mapping[str, Any]) -> str:
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


def _usage(payload: Mapping[str, Any]) -> dict[str, int]:
    raw = payload.get("usage")
    if not isinstance(raw, dict):
        return {}
    result: dict[str, int] = {}
    for key in ("input_tokens", "output_tokens", "total_tokens"):
        value = raw.get(key)
        if isinstance(value, int) and value >= 0:
            result[key] = value
    return result


class OpenAIResponsesProvider:
    """Tiny server-side Responses API client with an injectable transport for tests."""

    def __init__(self, config: LeadAIConfig, *, requester: JsonRequester = _default_requester) -> None:
        if config.provider != "openai":
            raise ValueError("OpenAIResponsesProvider requires provider='openai'")
        self.config = config
        self._requester = requester
        self.last_usage: dict[str, int] = {}
        self.last_response_id: str | None = None

    def complete_json(self, *, system: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        request_body = {
            "model": self.config.model,
            "input": [
                {"role": "system", "content": [{"type": "input_text", "text": system}]},
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": json.dumps(payload, ensure_ascii=False, separators=(",", ":"))}],
                },
            ],
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
        self.last_usage = _usage(raw)
        response_id = raw.get("id")
        self.last_response_id = str(response_id)[:120] if response_id else None
        text = _response_text(raw)
        try:
            result = json.loads(text)
        except json.JSONDecodeError as exc:
            raise RuntimeError("Lead AI response was not valid JSON") from exc
        if not isinstance(result, dict):
            raise RuntimeError("Lead AI response JSON must be an object")
        return result
