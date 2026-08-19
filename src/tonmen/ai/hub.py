from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from time import monotonic
from typing import Any, Mapping
from urllib.request import Request, urlopen


_ALLOWED_ACTIONS = {
    "continue_governed_plan",
    "await_human_approval",
    "review_failure_evidence",
    "finalize_report",
    "stop_for_human_review",
}

_ROLE_STRENGTH = {
    "surface_mapper": 1,
    "evidence_verifier": 2,
    "vulnerability_analyst": 3,
    "governance_reviewer": 1,
    "remediation_editor": 2,
}


@dataclass(frozen=True, slots=True)
class ProviderSpec:
    id: str
    label: str
    transport: str
    auth_mode: str
    strength: int
    cost_weight: float
    executable: str | None = None
    api_key_env: str | None = None
    base_url: str | None = None
    default_model: str | None = None
    login_command: tuple[str, ...] = ()
    probe_command: tuple[str, ...] = ()


@dataclass(slots=True)
class ProviderUsage:
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    estimated_calls: int = 0
    failures: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "calls": self.calls,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "estimated_calls": self.estimated_calls,
            "failures": self.failures,
        }


@dataclass(frozen=True, slots=True)
class RoutedReview:
    summary: str
    recommended_action: str
    confidence: float
    source: str
    provider: str | None = None
    model: str | None = None
    latency_ms: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    usage_estimated: bool = False
    error: str | None = None


_SPECS = {
    "openai": ProviderSpec(
        id="openai",
        label="OpenAI API",
        transport="responses_api",
        auth_mode="api_key",
        strength=3,
        cost_weight=3.0,
        api_key_env="OPENAI_API_KEY",
        base_url="https://api.openai.com/v1",
        default_model="gpt-5.6-terra",
    ),
    "chatgpt": ProviderSpec(
        id="chatgpt",
        label="ChatGPT / Codex",
        transport="codex_cli",
        auth_mode="browser_login",
        strength=3,
        cost_weight=1.0,
        executable="codex",
        default_model=None,
        login_command=("codex", "login"),
        probe_command=("codex", "login", "status"),
    ),
    "google": ProviderSpec(
        id="google",
        label="Google Antigravity",
        transport="antigravity_cli",
        auth_mode="browser_login",
        strength=3,
        cost_weight=1.0,
        executable="agy",
        default_model=None,
        login_command=("agy",),
        probe_command=("agy", "models"),
    ),
    "grok": ProviderSpec(
        id="grok",
        label="Grok / xAI",
        transport="grok_cli",
        auth_mode="browser_login",
        strength=3,
        cost_weight=1.0,
        executable="grok",
        default_model=None,
        login_command=("grok", "login"),
        probe_command=("grok", "models"),
    ),
    "deepseek": ProviderSpec(
        id="deepseek",
        label="DeepSeek API",
        transport="chat_completions",
        auth_mode="api_key",
        strength=3,
        cost_weight=0.35,
        api_key_env="DEEPSEEK_API_KEY",
        base_url="https://api.deepseek.com/v1",
        default_model="deepseek-v4-flash",
    ),
    "mistral": ProviderSpec(
        id="mistral",
        label="Mistral API",
        transport="chat_completions",
        auth_mode="api_key",
        strength=2,
        cost_weight=0.7,
        api_key_env="MISTRAL_API_KEY",
        base_url="https://api.mistral.ai/v1",
        default_model="mistral-small-2603",
    ),
}


def _split_pool(raw: str) -> tuple[str, ...]:
    values = []
    for item in raw.split(","):
        value = item.strip().lower()
        if value and value in _SPECS and value not in values:
            values.append(value)
    return tuple(values)


def _parse_weight_map(raw: str) -> dict[str, float]:
    result: dict[str, float] = {}
    for item in raw.split(","):
        key, sep, value = item.partition("=")
        if not sep:
            continue
        key = key.strip().lower()
        try:
            weight = float(value.strip())
        except ValueError:
            continue
        if key in _SPECS and weight > 0:
            result[key] = weight
    return result


def _extract_json_text(text: str) -> Mapping[str, Any]:
    value = text.strip()
    if not value:
        raise RuntimeError("provider returned an empty response")
    try:
        result = json.loads(value)
        if isinstance(result, dict):
            return result
    except json.JSONDecodeError:
        pass
    start = value.find("{")
    end = value.rfind("}")
    if start >= 0 and end > start:
        try:
            result = json.loads(value[start : end + 1])
        except json.JSONDecodeError as exc:
            raise RuntimeError("provider did not return valid JSON") from exc
        if isinstance(result, dict):
            return result
    raise RuntimeError("provider response JSON must be an object")


def _estimate_tokens(text: str) -> int:
    return max(1, round(len(text.encode("utf-8", errors="replace")) / 4))


class ProviderHub:
    """Explicit multi-provider pool for evidence-only AI review.

    Browser-login providers delegate authentication and credential storage to their
    official CLIs. TONMEN never reads those credential files. API-key providers read
    keys from environment variables only at request time.
    """

    def __init__(self, pool: tuple[str, ...] | None = None) -> None:
        configured = pool
        if configured is None:
            configured = _split_pool(os.getenv("TONMEN_AI_POOL", ""))
            if not configured and (os.getenv("TONMEN_AI_PROVIDER") or "").strip().lower() == "openai":
                configured = ("openai",)
        self.pool = configured
        self.weights = _parse_weight_map(os.getenv("TONMEN_AI_PROVIDER_WEIGHTS", ""))
        self.usage: dict[str, ProviderUsage] = {provider_id: ProviderUsage() for provider_id in _SPECS}
        self.token_budget = max(0, int(os.getenv("TONMEN_AI_SUBAGENT_TOKEN_BUDGET", "120000") or "120000"))

    @staticmethod
    def spec(provider_id: str) -> ProviderSpec:
        try:
            return _SPECS[provider_id]
        except KeyError as exc:
            raise ValueError(f"unknown AI provider: {provider_id}") from exc

    @staticmethod
    def _key_configured(spec: ProviderSpec) -> bool:
        return bool(spec.api_key_env and os.getenv(spec.api_key_env, "").strip())

    @staticmethod
    def _installed(spec: ProviderSpec) -> bool:
        return bool(spec.executable and shutil.which(spec.executable))

    def is_ready(self, provider_id: str) -> bool:
        spec = self.spec(provider_id)
        if spec.auth_mode == "api_key":
            return self._key_configured(spec)
        return self._installed(spec)

    def probe(self, provider_id: str, *, timeout: int = 8) -> dict[str, Any]:
        spec = self.spec(provider_id)
        if spec.auth_mode == "api_key":
            return {"ready": self._key_configured(spec), "detail": f"{spec.api_key_env} configured" if self._key_configured(spec) else f"set {spec.api_key_env}"}
        if not self._installed(spec):
            return {"ready": False, "detail": f"{spec.executable} is not installed"}
        if not spec.probe_command:
            return {"ready": True, "detail": "official CLI installed; authentication state not probed"}
        try:
            result = subprocess.run(
                list(spec.probe_command),
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return {"ready": False, "detail": str(exc)[:240]}
        detail = (result.stderr or result.stdout or "").strip().splitlines()
        return {
            "ready": result.returncode == 0,
            "detail": (detail[-1] if detail else f"exit {result.returncode}")[:240],
        }

    def launch_login(self, provider_id: str) -> dict[str, Any]:
        spec = self.spec(provider_id)
        if spec.auth_mode != "browser_login":
            raise ValueError(f"{provider_id} uses {spec.api_key_env}; browser login is not available")
        if not self._installed(spec):
            raise ValueError(f"{spec.executable} is not installed")
        if not spec.login_command:
            raise ValueError("provider has no login command")
        process = subprocess.Popen(list(spec.login_command), shell=False)  # noqa: S603 - fixed official CLI argv
        return {
            "provider": provider_id,
            "pid": process.pid,
            "command": list(spec.login_command),
            "note": "Authentication is handled by the official CLI. TONMEN does not read or persist its credentials.",
        }

    def public_status(self) -> dict[str, Any]:
        providers = []
        for provider_id, spec in _SPECS.items():
            probe = self.probe(provider_id, timeout=2) if provider_id in self.pool else None
            providers.append(
                {
                    "id": provider_id,
                    "label": spec.label,
                    "transport": spec.transport,
                    "auth_mode": spec.auth_mode,
                    "enabled_in_pool": provider_id in self.pool,
                    "installed": self._installed(spec) if spec.executable else None,
                    "key_env": spec.api_key_env,
                    "key_configured": self._key_configured(spec) if spec.api_key_env else None,
                    "default_model": self.model_for(provider_id),
                    "probe": probe,
                    "usage": self.usage[provider_id].as_dict(),
                    "secret_persisted_by_tonmen": False,
                    "secret_exposed_to_browser": False,
                }
            )
        return {
            "strategy": "weighted_least_usage",
            "pool": list(self.pool),
            "token_budget": self.token_budget,
            "provider_weights": {item: self.weights.get(item, 1.0) for item in self.pool},
            "providers": providers,
        }

    def model_for(self, provider_id: str, role: str | None = None) -> str | None:
        spec = self.spec(provider_id)
        if role:
            role_key = f"TONMEN_AI_ROUTE_{role.upper()}"
            route = (os.getenv(role_key) or "").strip()
            route_provider, sep, route_model = route.partition(":")
            if sep and route_provider.strip().lower() == provider_id and route_model.strip():
                return route_model.strip()
        env_key = f"TONMEN_AI_MODEL_{provider_id.upper()}"
        return (os.getenv(env_key) or spec.default_model or "").strip() or None

    def _explicit_route(self, role: str) -> tuple[str, str | None] | None:
        raw = (os.getenv(f"TONMEN_AI_ROUTE_{role.upper()}") or "").strip()
        provider_id, sep, model = raw.partition(":")
        provider_id = provider_id.strip().lower()
        if not provider_id:
            return None
        if provider_id not in self.pool or not self.is_ready(provider_id):
            return None
        return provider_id, model.strip() if sep and model.strip() else self.model_for(provider_id, role)

    def select(self, role: str) -> tuple[str, str | None] | None:
        explicit = self._explicit_route(role)
        if explicit:
            return explicit
        required = _ROLE_STRENGTH.get(role, 2)
        candidates = [provider_id for provider_id in self.pool if self.is_ready(provider_id)]
        if not candidates:
            return None
        if self.token_budget and sum(item.total_tokens for item in self.usage.values()) >= self.token_budget:
            return None

        def score(provider_id: str) -> tuple[float, float, str]:
            spec = self.spec(provider_id)
            usage = self.usage[provider_id]
            weight = self.weights.get(provider_id, 1.0)
            effective = (usage.total_tokens + usage.calls * 1000) / weight
            underpowered = max(0, required - spec.strength) * 1_000_000
            cost = spec.cost_weight * 250
            return (underpowered + effective + cost, effective, provider_id)

        chosen = min(candidates, key=score)
        return chosen, self.model_for(chosen, role)

    @staticmethod
    def _request_json(url: str, headers: Mapping[str, str], body: Mapping[str, Any], timeout: int = 45) -> Mapping[str, Any]:
        request = Request(url, data=json.dumps(body, ensure_ascii=False).encode("utf-8"), headers=dict(headers), method="POST")
        with urlopen(request, timeout=timeout) as response:  # nosec B310 - provider URLs are fixed constants
            payload = json.loads(response.read().decode("utf-8"))
        if not isinstance(payload, dict):
            raise RuntimeError("provider returned a non-object response")
        return payload

    def _http_complete(self, spec: ProviderSpec, model: str | None, system: str, payload: Mapping[str, Any]) -> tuple[Mapping[str, Any], dict[str, int], bool]:
        if not spec.api_key_env or not spec.base_url:
            raise RuntimeError("provider API configuration is incomplete")
        key = os.getenv(spec.api_key_env, "").strip()
        if not key:
            raise RuntimeError(f"{spec.api_key_env} is not configured")
        selected_model = model or spec.default_model
        if not selected_model:
            raise RuntimeError("provider model is not configured")

        if spec.transport == "responses_api":
            body = {
                "model": selected_model,
                "input": [
                    {"role": "system", "content": [{"type": "input_text", "text": system}]},
                    {"role": "user", "content": [{"type": "input_text", "text": json.dumps(payload, ensure_ascii=False, separators=(",", ":"))}]},
                ],
            }
            raw = self._request_json(
                f"{spec.base_url}/responses",
                {"Authorization": f"Bearer {key}", "Content-Type": "application/json", "Accept": "application/json"},
                body,
            )
            text = raw.get("output_text")
            if not isinstance(text, str):
                text = ""
                for item in raw.get("output", []) if isinstance(raw.get("output"), list) else []:
                    if not isinstance(item, dict) or item.get("type") != "message":
                        continue
                    for part in item.get("content", []) if isinstance(item.get("content"), list) else []:
                        if isinstance(part, dict) and part.get("type") == "output_text" and isinstance(part.get("text"), str):
                            text = part["text"]
                            break
            usage_raw = raw.get("usage") if isinstance(raw.get("usage"), dict) else {}
            usage = {
                "input_tokens": int(usage_raw.get("input_tokens") or 0),
                "output_tokens": int(usage_raw.get("output_tokens") or 0),
                "total_tokens": int(usage_raw.get("total_tokens") or 0),
            }
            return _extract_json_text(text), usage, False

        body = {
            "model": selected_model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False, separators=(",", ":"))},
            ],
            "response_format": {"type": "json_object"},
        }
        raw = self._request_json(
            f"{spec.base_url}/chat/completions",
            {"Authorization": f"Bearer {key}", "Content-Type": "application/json", "Accept": "application/json"},
            body,
        )
        choices = raw.get("choices") if isinstance(raw.get("choices"), list) else []
        message = choices[0].get("message") if choices and isinstance(choices[0], dict) else {}
        text = message.get("content") if isinstance(message, dict) else ""
        if isinstance(text, list):
            text = "".join(str(part.get("text", "")) for part in text if isinstance(part, dict))
        usage_raw = raw.get("usage") if isinstance(raw.get("usage"), dict) else {}
        input_tokens = int(usage_raw.get("prompt_tokens") or usage_raw.get("input_tokens") or 0)
        output_tokens = int(usage_raw.get("completion_tokens") or usage_raw.get("output_tokens") or 0)
        total_tokens = int(usage_raw.get("total_tokens") or input_tokens + output_tokens)
        return _extract_json_text(str(text or "")), {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
        }, False

    @staticmethod
    def _cli_prompt(system: str, payload: Mapping[str, Any]) -> str:
        return (
            system
            + "\nDo not inspect files, execute tools, browse, or modify the host. Analyze only the JSON input below. "
            + "Return only one JSON object.\nINPUT:\n"
            + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        )

    def _cli_complete(self, spec: ProviderSpec, model: str | None, system: str, payload: Mapping[str, Any]) -> tuple[Mapping[str, Any], dict[str, int], bool]:
        if not spec.executable or not shutil.which(spec.executable):
            raise RuntimeError(f"{spec.executable} is not installed")
        prompt = self._cli_prompt(system, payload)
        with tempfile.TemporaryDirectory(prefix="tonmen-ai-") as cwd:
            if spec.transport == "codex_cli":
                argv = [spec.executable, "exec", "--json", "--ephemeral", "--skip-git-repo-check", "--sandbox", "read-only", "-C", cwd]
                if model:
                    argv.extend(["--model", model])
                argv.append(prompt)
            elif spec.transport == "antigravity_cli":
                argv = [spec.executable, "--sandbox", "-p", prompt]
                if model:
                    argv.extend(["--model", model])
            elif spec.transport == "grok_cli":
                argv = [spec.executable, "--no-auto-update", "-p", prompt, "--output-format", "json", "--cwd", cwd]
                if model:
                    argv.extend(["-m", model])
            else:
                raise RuntimeError(f"unsupported CLI transport: {spec.transport}")
            result = subprocess.run(argv, capture_output=True, text=True, timeout=75, check=False, shell=False)  # noqa: S603
        if result.returncode != 0:
            raise RuntimeError((result.stderr or result.stdout or f"exit {result.returncode}").strip()[:500])

        text = result.stdout.strip()
        if spec.transport == "codex_cli":
            assistant_text = ""
            usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
            for line in text.splitlines():
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(event, dict):
                    continue
                raw_usage = event.get("usage") if isinstance(event.get("usage"), dict) else {}
                for key in usage:
                    value = raw_usage.get(key)
                    if isinstance(value, int):
                        usage[key] = max(usage[key], value)
                item = event.get("item") if isinstance(event.get("item"), dict) else {}
                if item.get("type") == "agent_message":
                    candidate = item.get("text") or item.get("content")
                    if isinstance(candidate, str):
                        assistant_text = candidate
            text = assistant_text or text
            estimated = not bool(usage["total_tokens"])
        else:
            usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
            if spec.transport == "grok_cli":
                try:
                    wrapper = json.loads(text)
                except json.JSONDecodeError:
                    wrapper = None
                if isinstance(wrapper, dict):
                    for key in ("response", "output", "text", "message"):
                        if isinstance(wrapper.get(key), str):
                            text = wrapper[key]
                            break
                    raw_usage = wrapper.get("usage") if isinstance(wrapper.get("usage"), dict) else {}
                    usage["input_tokens"] = int(raw_usage.get("input_tokens") or raw_usage.get("prompt_tokens") or 0)
                    usage["output_tokens"] = int(raw_usage.get("output_tokens") or raw_usage.get("completion_tokens") or 0)
                    usage["total_tokens"] = int(raw_usage.get("total_tokens") or usage["input_tokens"] + usage["output_tokens"])
            estimated = not bool(usage["total_tokens"])
        parsed = _extract_json_text(text)
        if estimated:
            usage["input_tokens"] = _estimate_tokens(prompt)
            usage["output_tokens"] = _estimate_tokens(text)
            usage["total_tokens"] = usage["input_tokens"] + usage["output_tokens"]
        return parsed, usage, estimated

    def complete_json(self, provider_id: str, model: str | None, *, system: str, payload: Mapping[str, Any]) -> tuple[Mapping[str, Any], dict[str, int], bool]:
        spec = self.spec(provider_id)
        if spec.transport in {"responses_api", "chat_completions"}:
            return self._http_complete(spec, model, system, payload)
        return self._cli_complete(spec, model, system, payload)

    def review(self, role: str, *, system: str, payload: Mapping[str, Any], fallback_summary: str, fallback_action: str) -> RoutedReview:
        selected = self.select(role)
        if selected is None:
            return RoutedReview(
                summary=fallback_summary,
                recommended_action=fallback_action,
                confidence=0.5,
                source="deterministic",
                error="no ready provider in explicit TONMEN_AI_POOL or token budget exhausted",
            )
        provider_id, model = selected
        started = monotonic()
        usage = self.usage[provider_id]
        try:
            result, token_usage, estimated = self.complete_json(provider_id, model, system=system, payload=payload)
            action = str(result.get("recommended_action") or fallback_action).strip().lower()
            if action not in _ALLOWED_ACTIONS:
                raise ValueError("subagent provider returned unsupported recommended_action")
            confidence = round(float(result.get("confidence", 0.5)), 2)
            if not 0 <= confidence <= 1:
                raise ValueError("subagent confidence must be between 0 and 1")
            summary = str(result.get("summary") or "").strip()[:1200]
            if not summary:
                raise ValueError("subagent provider returned an empty summary")
            usage.calls += 1
            usage.input_tokens += int(token_usage.get("input_tokens") or 0)
            usage.output_tokens += int(token_usage.get("output_tokens") or 0)
            usage.total_tokens += int(token_usage.get("total_tokens") or 0)
            if estimated:
                usage.estimated_calls += 1
            return RoutedReview(
                summary=summary,
                recommended_action=action,
                confidence=confidence,
                source="model",
                provider=provider_id,
                model=model,
                latency_ms=max(0, round((monotonic() - started) * 1000)),
                input_tokens=int(token_usage.get("input_tokens") or 0),
                output_tokens=int(token_usage.get("output_tokens") or 0),
                total_tokens=int(token_usage.get("total_tokens") or 0),
                usage_estimated=estimated,
            )
        except Exception as exc:
            usage.calls += 1
            usage.failures += 1
            return RoutedReview(
                summary=fallback_summary,
                recommended_action=fallback_action,
                confidence=0.5,
                source="deterministic",
                provider=provider_id,
                model=model,
                latency_ms=max(0, round((monotonic() - started) * 1000)),
                error=str(exc)[:500],
            )
