from __future__ import annotations

import json
import logging
import os
from time import monotonic
from typing import Any, Callable, Mapping

from .hub import ProviderHub as _ProviderHub
from .hub import ProviderSpec, RoutedReview

logger = logging.getLogger(__name__)

JsonValidator = Callable[[Mapping[str, Any]], None]

_PROVIDER_IDS = ("openai", "chatgpt", "google", "grok", "deepseek", "mistral")
_ROLES = (
    "surface_mapper",
    "evidence_verifier",
    "vulnerability_analyst",
    "governance_reviewer",
    "remediation_editor",
)
_ROLE_STRENGTH = {
    "surface_mapper": 1,
    "evidence_verifier": 2,
    "vulnerability_analyst": 3,
    "governance_reviewer": 1,
    "remediation_editor": 2,
}
_ALLOWED_ACTIONS = {
    "continue_governed_plan",
    "await_human_approval",
    "review_failure_evidence",
    "finalize_report",
    "stop_for_human_review",
}


class JsonCorrectionError(RuntimeError):
    def __init__(self, message: str, *, usage: Mapping[str, int]) -> None:
        super().__init__(message)
        self.usage = dict(usage)


def _parse_int_map(raw: str) -> dict[str, int]:
    result: dict[str, int] = {}
    for item in raw.split(","):
        key, sep, value = item.partition("=")
        if not sep:
            continue
        provider_id = key.strip().lower()
        if provider_id not in _PROVIDER_IDS:
            continue
        try:
            budget = int(value.strip())
        except ValueError:
            continue
        if budget >= 0:
            result[provider_id] = budget
    return result


def _enabled(name: str, default: bool = True) -> bool:
    raw = (os.getenv(name) or "").strip().lower()
    if not raw:
        return default
    return raw not in {"0", "false", "no", "off"}


def _confidence(value: float) -> float:
    return round(max(0.0, min(1.0, float(value))), 2)


def _strict_json_object(text: str) -> Mapping[str, Any]:
    result = json.loads(text.strip())
    if not isinstance(result, dict):
        raise ValueError("provider response JSON must be an object")
    return result


def _error_summary(exc: BaseException) -> str:
    detail = " ".join(str(exc).split())
    return f"{type(exc).__name__}: {detail}"[:800]


def _correction_message(exc: BaseException) -> str:
    return (
        "SYSTEM INTERCEPT: Your previous output failed validation. "
        f"{_error_summary(exc)}. "
        "Fix it immediately and return ONLY the raw valid JSON matching the required schema and constraints."
    )


def _merge_usage(total: dict[str, int], current: Mapping[str, Any]) -> None:
    for key in ("input_tokens", "output_tokens", "total_tokens"):
        value = current.get(key)
        if isinstance(value, int) and value >= 0:
            total[key] = total.get(key, 0) + value


class ProviderHub(_ProviderHub):
    """Explicit provider pool with quota-aware failover and safe public status.

    Multi-provider subagent calls require TONMEN_AI_POOL. `TONMEN_AI_POOL=auto` is
    an explicit opt-in that selects providers which are locally ready (API key set
    or official CLI installed). Merely enabling Lead AI still does not silently
    multiply model calls.

    Budgets are TONMEN-local guardrails, not claims about a provider account's real
    billing balance. A provider that fails repeatedly is avoided for the remainder
    of the current mission/council instance, while another ready provider may take
    over the evidence-only review.
    """

    def __init__(self, pool: tuple[str, ...] | None = None) -> None:
        self.pool_mode = "explicit"
        if pool is None:
            raw_pool = (os.getenv("TONMEN_AI_POOL") or "").strip()
            tokens = [item.strip().lower() for item in raw_pool.split(",") if item.strip()]
            if "auto" in tokens:
                self.pool_mode = "auto"
                values = []
                for provider_id in _PROVIDER_IDS:
                    spec = self.spec(provider_id)
                    ready = self._key_configured(spec) if spec.auth_mode == "api_key" else self._installed(spec)
                    if ready:
                        values.append(provider_id)
                pool = tuple(values)
            else:
                values = []
                for provider_id in tokens:
                    if provider_id == "auto" or provider_id in values:
                        continue
                    try:
                        self.spec(provider_id)
                    except ValueError:
                        continue
                    values.append(provider_id)
                pool = tuple(values)
        super().__init__(pool=pool)

        legacy_budget = self.token_budget
        raw_mission_budget = os.getenv("TONMEN_AI_MISSION_TOKEN_BUDGET")
        try:
            self.mission_token_budget = max(
                0,
                int(raw_mission_budget if raw_mission_budget is not None else legacy_budget),
            )
        except ValueError:
            self.mission_token_budget = max(0, int(legacy_budget))
        self.token_budget = self.mission_token_budget
        self.provider_token_budgets = _parse_int_map(os.getenv("TONMEN_AI_PROVIDER_TOKEN_BUDGETS", ""))
        try:
            self.failure_limit = max(1, int(os.getenv("TONMEN_AI_PROVIDER_FAILURE_LIMIT", "2") or "2"))
        except ValueError:
            self.failure_limit = 2
        self.failover_enabled = _enabled("TONMEN_AI_FAILOVER", True)
        self.strict_routes = _enabled("TONMEN_AI_ROUTE_STRICT", False)
        self._seeded_run_id: str | None = None
        self.failover_events = 0

    def prime_usage_from_run(self, run: Any) -> None:
        """Rebuild current-mission usage from persisted Council graph nodes once.

        This makes the mission token budget survive MissionLoop resume/restart. Only
        model-subagent metadata is inspected; raw Evidence is never read or sent.
        """
        run_id = str(getattr(run, "id", "") or "")
        if not run_id or run_id == self._seeded_run_id:
            return
        for item in self.usage.values():
            item.calls = 0
            item.input_tokens = 0
            item.output_tokens = 0
            item.total_tokens = 0
            item.estimated_calls = 0
            item.failures = 0
        graph = getattr(run, "graph", None)
        nodes = getattr(graph, "nodes", {}) if graph is not None else {}
        for node in nodes.values():
            if getattr(node, "kind", None) != "council.subagent":
                continue
            metadata = getattr(node, "metadata", {}) or {}
            provider_id = metadata.get("provider")
            if not isinstance(provider_id, str) or provider_id not in self.usage:
                continue
            usage = self.usage[provider_id]
            if metadata.get("source") == "model":
                usage.calls += 1
                for key in ("input_tokens", "output_tokens", "total_tokens"):
                    value = metadata.get(key)
                    if isinstance(value, int) and value > 0:
                        setattr(usage, key, getattr(usage, key) + value)
                if metadata.get("usage_estimated"):
                    usage.estimated_calls += 1
            if metadata.get("provider_error") and metadata.get("source") != "model":
                usage.calls += 1
                usage.failures += 1
        self._seeded_run_id = run_id

    def _mission_tokens_used(self) -> int:
        return sum(item.total_tokens for item in self.usage.values())

    def _provider_budget(self, provider_id: str) -> int | None:
        value = self.provider_token_budgets.get(provider_id)
        return value if value is not None and value > 0 else None

    def _provider_remaining(self, provider_id: str) -> int | None:
        budget = self._provider_budget(provider_id)
        if budget is None:
            return None
        return max(0, budget - self.usage[provider_id].total_tokens)

    def _within_budget(self, provider_id: str) -> bool:
        if self.mission_token_budget and self._mission_tokens_used() >= self.mission_token_budget:
            return False
        remaining = self._provider_remaining(provider_id)
        return remaining is None or remaining > 0

    def _healthy(self, provider_id: str) -> bool:
        return self.usage[provider_id].failures < self.failure_limit

    def _explicit_route(self, role: str) -> tuple[str, str | None] | None:
        raw = (os.getenv(f"TONMEN_AI_ROUTE_{role.upper()}") or "").strip()
        provider_id, sep, model = raw.partition(":")
        provider_id = provider_id.strip().lower()
        if not provider_id:
            return None
        if (
            provider_id not in self.pool
            or not self.is_ready(provider_id)
            or not self._within_budget(provider_id)
            or not self._healthy(provider_id)
        ):
            return None
        return provider_id, model.strip() if sep and model.strip() else self.model_for(provider_id, role)

    def _score(self, provider_id: str, role: str) -> tuple[float, float, str]:
        spec = self.spec(provider_id)
        usage = self.usage[provider_id]
        weight = self.weights.get(provider_id, 1.0)
        effective = (usage.total_tokens + usage.calls * 1000) / weight
        required = _ROLE_STRENGTH.get(role, 2)
        underpowered = max(0, required - spec.strength) * 1_000_000
        budget = self._provider_budget(provider_id)
        quota_pressure = 0.0
        if budget:
            quota_pressure = min(1.0, usage.total_tokens / budget) * 250_000
        failure_pressure = usage.failures * 150_000
        cost = spec.cost_weight * 250
        return (underpowered + quota_pressure + failure_pressure + effective + cost, effective, provider_id)

    def ordered_candidates(self, role: str, *, exclude: set[str] | None = None) -> list[tuple[str, str | None]]:
        excluded = exclude or set()
        explicit = self._explicit_route(role)
        result: list[tuple[str, str | None]] = []
        if explicit and explicit[0] not in excluded:
            result.append(explicit)
            if self.strict_routes:
                return result
        elif self.strict_routes and (os.getenv(f"TONMEN_AI_ROUTE_{role.upper()}") or "").strip():
            return []

        candidates = [
            provider_id
            for provider_id in self.pool
            if provider_id not in excluded
            and (not explicit or provider_id != explicit[0])
            and self.is_ready(provider_id)
            and self._within_budget(provider_id)
            and self._healthy(provider_id)
        ]
        for provider_id in sorted(candidates, key=lambda item: self._score(item, role)):
            result.append((provider_id, self.model_for(provider_id, role)))
        return result

    def select(self, role: str) -> tuple[str, str | None] | None:
        candidates = self.ordered_candidates(role)
        return candidates[0] if candidates else None

    @staticmethod
    def _validate_review_result(result: Mapping[str, Any]) -> None:
        action = str(result.get("recommended_action") or "").strip().lower()
        if action not in _ALLOWED_ACTIONS:
            raise ValueError("subagent provider returned unsupported recommended_action")
        try:
            confidence = float(result.get("confidence", 0.5))
        except (TypeError, ValueError) as exc:
            raise ValueError("subagent confidence must be a number between 0 and 1") from exc
        if not 0 <= confidence <= 1:
            raise ValueError("subagent confidence must be between 0 and 1")
        summary = str(result.get("summary") or "").strip()
        if not summary:
            raise ValueError("subagent provider returned an empty summary")

    def _http_complete_with_retries(
        self,
        spec: ProviderSpec,
        model: str | None,
        system: str,
        payload: Mapping[str, Any],
        *,
        validator: JsonValidator,
        max_retries: int,
    ) -> tuple[Mapping[str, Any], dict[str, int], bool]:
        if not isinstance(max_retries, int) or isinstance(max_retries, bool) or max_retries < 1:
            raise ValueError("max_retries must be an integer >= 1")
        if not spec.api_key_env or not spec.base_url:
            raise RuntimeError("provider API configuration is incomplete")
        key = os.getenv(spec.api_key_env, "").strip()
        if not key:
            raise RuntimeError(f"{spec.api_key_env} is not configured")
        selected_model = model or spec.default_model
        if not selected_model:
            raise RuntimeError("provider model is not configured")

        cumulative_usage: dict[str, int] = {}
        last_error: BaseException | None = None

        if spec.transport == "responses_api":
            input_items: list[dict[str, Any]] = [
                {"role": "system", "content": [{"type": "input_text", "text": system}]},
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": json.dumps(payload, ensure_ascii=False, separators=(",", ":"))}],
                },
            ]
            for attempt in range(1, max_retries + 1):
                raw = self._request_json(
                    f"{spec.base_url}/responses",
                    {"Authorization": f"Bearer {key}", "Content-Type": "application/json", "Accept": "application/json"},
                    {"model": selected_model, "input": input_items},
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
                _merge_usage(
                    cumulative_usage,
                    {
                        "input_tokens": int(usage_raw.get("input_tokens") or 0),
                        "output_tokens": int(usage_raw.get("output_tokens") or 0),
                        "total_tokens": int(usage_raw.get("total_tokens") or 0),
                    },
                )
                try:
                    result = _strict_json_object(str(text or ""))
                    validator(result)
                    return result, cumulative_usage, False
                except (json.JSONDecodeError, ValueError) as exc:
                    last_error = exc
                    if attempt >= max_retries:
                        break
                    logger.warning(
                        "SYSTEM INTERCEPT provider=%s attempt=%d/%d validation_failed=%s",
                        spec.id,
                        attempt,
                        max_retries,
                        _error_summary(exc),
                    )
                    input_items.extend(
                        [
                            {"role": "assistant", "content": [{"type": "input_text", "text": str(text or "")}]},
                            {"role": "system", "content": [{"type": "input_text", "text": _correction_message(exc)}]},
                        ]
                    )
        else:
            messages: list[dict[str, str]] = [
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False, separators=(",", ":"))},
            ]
            for attempt in range(1, max_retries + 1):
                raw = self._request_json(
                    f"{spec.base_url}/chat/completions",
                    {"Authorization": f"Bearer {key}", "Content-Type": "application/json", "Accept": "application/json"},
                    {
                        "model": selected_model,
                        "messages": messages,
                        "response_format": {"type": "json_object"},
                    },
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
                _merge_usage(
                    cumulative_usage,
                    {
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                        "total_tokens": total_tokens,
                    },
                )
                try:
                    result = _strict_json_object(str(text or ""))
                    validator(result)
                    return result, cumulative_usage, False
                except (json.JSONDecodeError, ValueError) as exc:
                    last_error = exc
                    if attempt >= max_retries:
                        break
                    logger.warning(
                        "SYSTEM INTERCEPT provider=%s attempt=%d/%d validation_failed=%s",
                        spec.id,
                        attempt,
                        max_retries,
                        _error_summary(exc),
                    )
                    messages.extend(
                        [
                            {"role": "assistant", "content": str(text or "")},
                            {"role": "user", "content": _correction_message(exc)},
                        ]
                    )

        raise JsonCorrectionError(
            f"{spec.id} failed JSON validation after {max_retries} attempts: "
            f"{_error_summary(last_error or RuntimeError('validation failed'))}",
            usage=cumulative_usage,
        ) from last_error

    def complete_json(
        self,
        provider_id: str,
        model: str | None,
        *,
        system: str,
        payload: Mapping[str, Any],
        validator: JsonValidator | None = None,
        max_retries: int = 3,
    ) -> tuple[Mapping[str, Any], dict[str, int], bool]:
        spec = self.spec(provider_id)
        if spec.transport in {"responses_api", "chat_completions"}:
            return self._http_complete_with_retries(
                spec,
                model,
                system,
                payload,
                validator=validator or self._validate_review_result,
                max_retries=max_retries,
            )
        result, token_usage, estimated = self._cli_complete(spec, model, system, payload)
        if validator is not None:
            validator(result)
        return result, token_usage, estimated

    def review(
        self,
        role: str,
        *,
        system: str,
        payload: Mapping[str, Any],
        fallback_summary: str,
        fallback_action: str,
        fallback_confidence: float = 0.5,
    ) -> RoutedReview:
        fallback_confidence = _confidence(fallback_confidence)
        if self.mission_token_budget and self._mission_tokens_used() >= self.mission_token_budget:
            return RoutedReview(
                summary=fallback_summary,
                recommended_action=fallback_action,
                confidence=_confidence(min(fallback_confidence, 0.45)),
                source="deterministic",
                error="TONMEN mission AI token budget exhausted",
            )

        candidates = self.ordered_candidates(role)
        if not candidates:
            if not self.pool:
                error = "AI subagent pool disabled; set TONMEN_AI_POOL=auto or an explicit provider list"
            else:
                error = "no ready provider within TONMEN mission/provider budgets"
            return RoutedReview(
                summary=fallback_summary,
                recommended_action=fallback_action,
                confidence=fallback_confidence,
                source="deterministic",
                error=error,
            )

        failures: list[str] = []
        last_provider: str | None = None
        last_model: str | None = None
        started_all = monotonic()
        for index, (provider_id, model) in enumerate(candidates):
            last_provider, last_model = provider_id, model
            usage = self.usage[provider_id]
            started = monotonic()
            try:
                result, token_usage, estimated = self.complete_json(
                    provider_id,
                    model,
                    system=system,
                    payload=payload,
                )
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
                if failures:
                    self.failover_events += 1
                recovery = None
                if failures:
                    recovery = "failover recovered after " + "; ".join(failures)[:420]
                return RoutedReview(
                    summary=summary,
                    recommended_action=action,
                    confidence=confidence,
                    source="model",
                    provider=provider_id,
                    model=model,
                    latency_ms=max(0, round((monotonic() - started_all) * 1000)),
                    input_tokens=int(token_usage.get("input_tokens") or 0),
                    output_tokens=int(token_usage.get("output_tokens") or 0),
                    total_tokens=int(token_usage.get("total_tokens") or 0),
                    usage_estimated=estimated,
                    error=recovery,
                )
            except Exception as exc:
                retry_usage = getattr(exc, "usage", None)
                if isinstance(retry_usage, dict):
                    usage.input_tokens += int(retry_usage.get("input_tokens") or 0)
                    usage.output_tokens += int(retry_usage.get("output_tokens") or 0)
                    usage.total_tokens += int(retry_usage.get("total_tokens") or 0)
                usage.calls += 1
                usage.failures += 1
                failures.append(f"{provider_id}: {str(exc)[:140]}")
                if not self.failover_enabled or index + 1 >= len(candidates):
                    break
                _ = started

        return RoutedReview(
            summary=fallback_summary,
            recommended_action=fallback_action,
            confidence=_confidence(max(0.15, fallback_confidence - 0.1)),
            source="deterministic",
            provider=last_provider,
            model=last_model,
            latency_ms=max(0, round((monotonic() - started_all) * 1000)),
            error=("all eligible providers failed: " + "; ".join(failures))[:500],
        )

    def public_status(self) -> dict[str, object]:
        providers: list[dict[str, object]] = []
        for provider_id in _PROVIDER_IDS:
            spec = self.spec(provider_id)
            remaining = self._provider_remaining(provider_id)
            providers.append(
                {
                    "id": provider_id,
                    "label": spec.label,
                    "transport": spec.transport,
                    "auth_mode": spec.auth_mode,
                    "strength": spec.strength,
                    "cost_weight": spec.cost_weight,
                    "enabled_in_pool": provider_id in self.pool,
                    "installed": self._installed(spec) if spec.executable else None,
                    "executable": spec.executable,
                    "key_env": spec.api_key_env,
                    "key_configured": self._key_configured(spec) if spec.api_key_env else None,
                    "default_model": self.model_for(provider_id),
                    "usage": self.usage[provider_id].as_dict(),
                    "tonmen_token_budget": self._provider_budget(provider_id),
                    "tonmen_tokens_remaining": remaining,
                    "healthy_for_mission": self._healthy(provider_id),
                    "secret_persisted_by_tonmen": False,
                    "secret_exposed_to_browser": False,
                    "probe_is_explicit": True,
                }
            )
        routes = {
            role: (os.getenv(f"TONMEN_AI_ROUTE_{role.upper()}") or "").strip()
            for role in _ROLES
        }
        mission_used = self._mission_tokens_used()
        mission_remaining = (
            max(0, self.mission_token_budget - mission_used)
            if self.mission_token_budget
            else None
        )
        warning = None
        if not self.pool:
            warning = "Council model pool is disabled. Set TONMEN_AI_POOL=auto or a comma-separated provider list to enable model-backed subagents."
        return {
            "strategy": "quota_aware_failover",
            "pool": list(self.pool),
            "pool_mode": self.pool_mode,
            "configuration_warning": warning,
            "token_budget": self.mission_token_budget,
            "mission_token_budget": self.mission_token_budget,
            "mission_tokens_used": mission_used,
            "mission_tokens_remaining": mission_remaining,
            "provider_token_budgets": dict(self.provider_token_budgets),
            "provider_failure_limit": self.failure_limit,
            "failover_enabled": self.failover_enabled,
            "strict_routes": self.strict_routes,
            "failover_events": self.failover_events,
            "provider_weights": {item: self.weights.get(item, 1.0) for item in self.pool},
            "role_routes": routes,
            "providers": providers,
            "privacy": {
                "credential_values_exposed": False,
                "credential_files_read_by_tonmen": False,
                "raw_evidence_sent": False,
                "approval_tokens_sent": False,
            },
        }
