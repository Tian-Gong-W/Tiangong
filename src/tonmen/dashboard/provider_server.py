from __future__ import annotations

import json
import os
import secrets
import threading
import webbrowser
from http.server import ThreadingHTTPServer
from importlib import resources
from typing import Any
from urllib.parse import unquote, urlparse

from tonmen.ai import ProviderHub
from tonmen.core.config import TonmenConfig
from tonmen.workers import RemoteWorkerExecutor, WorkerHTTPTransport, WorkerPool

from .server import DashboardState as BaseDashboardState
from .server import TonmenDashboardHandler, validate_console_host

_PROVIDER_ASSETS = {
    "provider-hub-page.css": "text/css; charset=utf-8",
    "provider-hub-page.js": "text/javascript; charset=utf-8",
    "worker-fleet-page.css": "text/css; charset=utf-8",
    "worker-fleet-page.js": "text/javascript; charset=utf-8",
}


class DashboardState(BaseDashboardState):
    """Dashboard facade extended with credential-safe AI and Worker control planes."""

    def __init__(self, config: TonmenConfig) -> None:
        super().__init__(config)
        self._provider_probes: dict[str, dict[str, Any]] = {}
        self._worker_probes: dict[str, dict[str, Any]] = {}

    @staticmethod
    def _empty_usage() -> dict[str, int]:
        return {
            "calls": 0,
            "model_calls": 0,
            "fallback_calls": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "estimated_calls": 0,
            "failures": 0,
        }

    def provider_hub(self) -> dict[str, Any]:
        """Return pool configuration plus persisted per-provider usage.

        Credential values are never returned. Browser-login credential stores are
        owned by their official CLIs and are not read by TONMEN.
        """
        with self._lock:
            hub = ProviderHub()
            payload = dict(hub.public_status())
            usage: dict[str, dict[str, int]] = {
                str(item["id"]): self._empty_usage()
                for item in payload.get("providers", [])
                if isinstance(item, dict) and item.get("id")
            }

            for entry in list(self.chronicle.list())[:100]:
                try:
                    _, run = self.chronicle.load(entry.run_id)
                except (FileNotFoundError, ValueError, OSError):
                    continue
                for node in run.graph.nodes.values():
                    if node.kind != "council.subagent":
                        continue
                    metadata = node.metadata
                    provider_id = metadata.get("provider")
                    if not isinstance(provider_id, str) or provider_id not in usage:
                        continue
                    item = usage[provider_id]
                    item["calls"] += 1
                    if metadata.get("source") == "model":
                        item["model_calls"] += 1
                    else:
                        item["fallback_calls"] += 1
                    if metadata.get("usage_estimated"):
                        item["estimated_calls"] += 1
                    if metadata.get("provider_error"):
                        item["failures"] += 1
                    for key in ("input_tokens", "output_tokens", "total_tokens"):
                        value = metadata.get(key)
                        if isinstance(value, int) and value > 0:
                            item[key] += value

            total_tokens = sum(item["total_tokens"] for item in usage.values())
            total_calls = sum(item["calls"] for item in usage.values())
            distribution = []
            for provider_id, item in usage.items():
                token_share = round(item["total_tokens"] * 100 / total_tokens, 1) if total_tokens else 0.0
                call_share = round(item["calls"] * 100 / total_calls, 1) if total_calls else 0.0
                distribution.append(
                    {
                        "provider": provider_id,
                        "tokens": item["total_tokens"],
                        "calls": item["calls"],
                        "token_share_percent": token_share,
                        "call_share_percent": call_share,
                    }
                )

            providers = []
            for provider in payload.get("providers", []):
                if not isinstance(provider, dict):
                    continue
                item = dict(provider)
                provider_id = str(item.get("id") or "")
                item["usage"] = usage.get(provider_id, self._empty_usage())
                item["last_probe"] = self._provider_probes.get(provider_id)
                providers.append(item)

            payload["providers"] = providers
            payload["historical_usage"] = {
                "missions_considered": min(100, len(self.chronicle.list())),
                "total_calls": total_calls,
                "total_tokens": total_tokens,
                "providers": usage,
            }
            payload["distribution"] = distribution
            payload["authority"] = {
                "execution": False,
                "approval": False,
                "scope": False,
                "plan_mutation": False,
            }
            return payload

    def probe_provider(self, provider_id: str) -> dict[str, Any]:
        with self._lock:
            hub = ProviderHub()
            spec = hub.spec(provider_id)
            raw = hub.probe(provider_id)
            ready = bool(raw.get("ready"))
            if spec.auth_mode == "browser_login":
                installed = hub._installed(spec)
                detail = (
                    "official CLI reports authenticated / ready"
                    if ready
                    else f"{spec.executable} is not installed"
                    if not installed
                    else "official CLI did not confirm an authenticated session"
                )
            else:
                detail = f"{spec.api_key_env} configured" if ready else f"set {spec.api_key_env} on the TONMEN server"
            result = {
                "provider": provider_id,
                "ready": ready,
                "detail": detail,
                "auth_mode": spec.auth_mode,
            }
            self._provider_probes[provider_id] = result
            self.events.publish("ai.provider_probed", provider=provider_id, ready=ready, auth_mode=spec.auth_mode)
            return result

    def launch_provider_login(self, provider_id: str) -> dict[str, Any]:
        with self._lock:
            hub = ProviderHub()
            spec = hub.spec(provider_id)
            launched = hub.launch_login(provider_id)
            self._provider_probes[provider_id] = {
                "provider": provider_id,
                "ready": False,
                "detail": "login flow launched; finish authentication in the official browser/CLI, then check connection",
                "auth_mode": spec.auth_mode,
            }
            self.events.publish("ai.provider_login_started", provider=provider_id, auth_mode=spec.auth_mode)
            return {
                "provider": provider_id,
                "label": spec.label,
                "pid": launched.get("pid"),
                "auth_mode": spec.auth_mode,
                "note": "Authentication is handled by the official CLI; TONMEN does not read or persist its credentials.",
            }

    def _worker_pool(self) -> WorkerPool:
        return self.runtime.workers if self.runtime.workers is not None else WorkerPool.from_env()

    def worker_fleet(self) -> dict[str, Any]:
        """Return worker configuration and Chronicle provenance without probing remote nodes."""
        with self._lock:
            pool = self._worker_pool()
            payload = pool.public_status()
            history: dict[str, dict[str, int]] = {
                item.id: {"steps": 0, "succeeded": 0, "failed": 0, "evidence": 0}
                for item in pool.workers
            }
            remote_steps = 0
            evidence_records = 0
            missions_considered = 0
            for entry in list(self.chronicle.list())[:100]:
                try:
                    _, run = self.chronicle.load(entry.run_id)
                except (FileNotFoundError, ValueError, OSError):
                    continue
                missions_considered += 1
                for execution in run.steps:
                    worker_id = execution.metadata.get("worker_id")
                    if not isinstance(worker_id, str) or not worker_id:
                        continue
                    remote_steps += 1
                    item = history.setdefault(worker_id, {"steps": 0, "succeeded": 0, "failed": 0, "evidence": 0})
                    item["steps"] += 1
                    if execution.state.value in {"succeeded", "degraded"}:
                        item["succeeded"] += 1
                    elif execution.state.value in {"failed", "denied"}:
                        item["failed"] += 1
                    if execution.evidence_id:
                        item["evidence"] += 1
                        evidence_records += 1

            workers = []
            for worker in payload.get("workers", []):
                item = dict(worker)
                worker_id = str(item.get("id") or "")
                item["history"] = history.get(worker_id, {"steps": 0, "succeeded": 0, "failed": 0, "evidence": 0})
                item["last_probe"] = self._worker_probes.get(worker_id)
                workers.append(item)

            executor = self.runtime.executor
            execution_mode = "worker" if isinstance(executor, RemoteWorkerExecutor) else "local"
            tag_text = os.getenv("TONMEN_WORKER_TAGS", "")
            payload.update(
                {
                    "execution_mode": execution_mode,
                    "workers": workers,
                    "historical": {
                        "missions_considered": missions_considered,
                        "remote_steps": remote_steps,
                        "evidence_records": evidence_records,
                        "workers": history,
                    },
                    "routing": {
                        "probe_before_dispatch": bool(getattr(executor, "probe_before_dispatch", True)),
                        "job_ttl_seconds": int(getattr(executor, "job_ttl_seconds", os.getenv("TONMEN_WORKER_JOB_TTL_SECONDS", "60") or "60")),
                        "worker_id": os.getenv("TONMEN_WORKER_ID", "").strip(),
                        "region": os.getenv("TONMEN_WORKER_REGION", "").strip(),
                        "tags": [item.strip() for item in tag_text.split(",") if item.strip()],
                        "automatic_cross_worker_retry_after_dispatch": False,
                    },
                    "privacy": {
                        "secret_values_exposed": False,
                        "approval_tokens_sent": False,
                        "raw_shell_sent": False,
                        "raw_argv_sent": False,
                    },
                }
            )
            return payload

    def probe_worker(self, worker_id: str) -> dict[str, Any]:
        with self._lock:
            pool = self._worker_pool()
            spec = pool.get(worker_id)
            transport = self.runtime.executor.transport if isinstance(self.runtime.executor, RemoteWorkerExecutor) else WorkerHTTPTransport(timeout_seconds=self.config.command_timeout_seconds + 30)
            try:
                raw = dict(transport.health(spec, timeout=5))
                remote = raw.get("worker") if isinstance(raw.get("worker"), dict) else {}
                identity_ok = str(remote.get("id") or "").strip().lower() == spec.id
                tools_raw = raw.get("tools") if isinstance(raw.get("tools"), dict) else {}
                tools = {
                    str(name): {"ready": bool(value.get("ready")), "code": str(value.get("code") or "")}
                    for name, value in tools_raw.items()
                    if isinstance(value, dict)
                }
                ready = bool(raw.get("ok")) and identity_ok
                detail = (
                    f"worker ready in {remote.get('region') or spec.region}"
                    if ready
                    else "worker health identity mismatch"
                )
                result = {
                    "worker": spec.id,
                    "ready": ready,
                    "detail": detail,
                    "region": str(remote.get("region") or spec.region),
                    "tags": list(remote.get("tags") or spec.tags),
                    "ready_tools": int(raw.get("ready_tools") or sum(1 for item in tools.values() if item["ready"])),
                    "total_tools": int(raw.get("total_tools") or len(tools)),
                    "tools": tools,
                    "governance": dict(raw.get("governance") or {}),
                }
            except Exception as exc:
                result = {
                    "worker": spec.id,
                    "ready": False,
                    "detail": str(exc)[:300],
                    "region": spec.region,
                    "tags": list(spec.tags),
                    "ready_tools": 0,
                    "total_tools": 0,
                    "tools": {},
                    "governance": {},
                }
            self._worker_probes[spec.id] = result
            self.events.publish("worker.probed", worker_id=spec.id, ready=result["ready"], region=spec.region)
            return result


class ProviderDashboardHandler(TonmenDashboardHandler):
    """Adds Provider Hub and Worker Fleet UI/API while preserving the governed base Console."""

    def _provider_index(self) -> bytes:
        text = resources.files("tonmen.dashboard.static").joinpath("provider-hub-page.html").read_text(encoding="utf-8")
        return text.replace("__TONMEN_CSRF__", self.server.csrf_token).encode("utf-8")

    def _worker_index(self) -> bytes:
        text = resources.files("tonmen.dashboard.static").joinpath("worker-fleet-page.html").read_text(encoding="utf-8")
        return text.replace("__TONMEN_CSRF__", self.server.csrf_token).encode("utf-8")

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        try:
            if path == "/lead":
                self._send_bytes(200, "text/html; charset=utf-8", self._provider_index())
                return
            if path == "/workers":
                self._send_bytes(200, "text/html; charset=utf-8", self._worker_index())
                return
            if path.startswith("/assets/"):
                name = unquote(path.removeprefix("/assets/"))
                content_type = _PROVIDER_ASSETS.get(name)
                if content_type is not None:
                    payload = resources.files("tonmen.dashboard.static").joinpath(name).read_bytes()
                    self._send_bytes(200, content_type, payload, cache="no-store")
                    return
            if path == "/api/ai/providers":
                self._json(200, self.server.state.provider_hub())
                return
            if path == "/api/workers":
                self._json(200, self.server.state.worker_fleet())
                return
        except (ValueError, OSError, json.JSONDecodeError) as exc:
            self._error(400, str(exc))
            return
        except Exception as exc:
            self._error(500, f"control-plane workspace error: {exc}")
            return
        super().do_GET()

    def do_POST(self) -> None:
        path = urlparse(self.path).path.rstrip("/")
        parts = path.split("/")
        is_provider_action = len(parts) == 6 and parts[1:4] == ["api", "ai", "providers"] and parts[5] in {"login", "probe"}
        is_worker_probe = len(parts) == 5 and parts[1:3] == ["api", "workers"] and parts[4] == "probe"
        if not is_provider_action and not is_worker_probe:
            super().do_POST()
            return
        if not self._csrf_ok():
            self._error(403, "invalid local CSRF token or origin")
            return
        try:
            if is_worker_probe:
                worker_id = unquote(parts[3]).strip().lower()
                self._json(200, self.server.state.probe_worker(worker_id))
                return
            provider_id = unquote(parts[4]).strip().lower()
            if parts[5] == "login":
                self._json(200, self.server.state.launch_provider_login(provider_id))
            else:
                self._json(200, self.server.state.probe_provider(provider_id))
        except (ValueError, OSError, KeyError) as exc:
            self._error(400, str(exc))
        except Exception as exc:
            self._error(500, f"control-plane workspace error: {exc}")


class ProviderDashboardServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, state: DashboardState):
        self.state = state
        self.csrf_token = secrets.token_urlsafe(32)
        super().__init__(address, ProviderDashboardHandler)


def serve_dashboard(
    config: TonmenConfig,
    *,
    host: str = "127.0.0.1",
    port: int | None = None,
    open_browser: bool = True,
) -> int:
    host = validate_console_host(host)
    bind_port = int(port if port is not None else config.bind_port)
    if not 1 <= bind_port <= 65535:
        raise ValueError("console port must be within 1-65535")
    server = ProviderDashboardServer((host, bind_port), DashboardState(config))
    display_host = "127.0.0.1" if host in {"127.0.0.1", "localhost"} else "[::1]"
    url = f"http://{display_host}:{server.server_address[1]}/"
    print(f"雲頂天宮 Console: {url}")
    print("本地控制面板僅綁定 loopback；Ctrl+C 停止。")
    if open_browser:
        threading.Timer(0.2, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        print("\n天宮已閉。")
    finally:
        server.server_close()
    return 0
