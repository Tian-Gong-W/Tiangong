from __future__ import annotations

import json
import secrets
import threading
import webbrowser
from http.server import ThreadingHTTPServer
from importlib import resources
from typing import Any
from urllib.parse import unquote, urlparse

from tonmen.ai import ProviderHub
from tonmen.core.config import TonmenConfig

from .server import DashboardState as BaseDashboardState
from .server import TonmenDashboardHandler, validate_console_host

_PROVIDER_ASSETS = {
    "provider-hub-page.css": "text/css; charset=utf-8",
    "provider-hub-page.js": "text/javascript; charset=utf-8",
}


class DashboardState(BaseDashboardState):
    """Dashboard facade extended with a credential-safe AI Provider Hub."""

    def __init__(self, config: TonmenConfig) -> None:
        super().__init__(config)
        self._provider_probes: dict[str, dict[str, Any]] = {}

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


class ProviderDashboardHandler(TonmenDashboardHandler):
    """Adds Provider Hub UI/API while preserving the governed base Console."""

    def _provider_index(self) -> bytes:
        text = resources.files("tonmen.dashboard.static").joinpath("provider-hub-page.html").read_text(encoding="utf-8")
        return text.replace("__TONMEN_CSRF__", self.server.csrf_token).encode("utf-8")

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        try:
            if path == "/lead":
                self._send_bytes(200, "text/html; charset=utf-8", self._provider_index())
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
        except (ValueError, OSError, json.JSONDecodeError) as exc:
            self._error(400, str(exc))
            return
        except Exception as exc:
            self._error(500, f"provider hub error: {exc}")
            return
        super().do_GET()

    def do_POST(self) -> None:
        path = urlparse(self.path).path.rstrip("/")
        parts = path.split("/")
        is_provider_action = len(parts) == 6 and parts[1:4] == ["api", "ai", "providers"] and parts[5] in {"login", "probe"}
        if not is_provider_action:
            super().do_POST()
            return
        if not self._csrf_ok():
            self._error(403, "invalid local CSRF token or origin")
            return
        provider_id = unquote(parts[4]).strip().lower()
        try:
            if parts[5] == "login":
                self._json(200, self.server.state.launch_provider_login(provider_id))
            else:
                self._json(200, self.server.state.probe_provider(provider_id))
        except (ValueError, OSError) as exc:
            self._error(400, str(exc))
        except Exception as exc:
            self._error(500, f"provider hub error: {exc}")


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
