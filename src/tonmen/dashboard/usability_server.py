from __future__ import annotations

import json
import os
import re
import secrets
import threading
import webbrowser
from http.server import ThreadingHTTPServer
from importlib import resources
from typing import Any
from urllib.parse import unquote, urlparse

from tonmen.ai import ProviderHub
from tonmen.ai.secrets import clear_secret, public_secret_status, set_secret
from tonmen.ai.settings import apply_local_ai_environment, public_settings, update_settings
from tonmen.core.config import TonmenConfig
from tonmen.loop import MissionLoop
from tonmen.missions import MissionRunState

from .preflight_server import DashboardState as PreflightDashboardState
from .preflight_server import MissionPreflightDashboardHandler
from .server import _waiting_step, mission_payload, validate_console_host

_USABILITY_ASSETS = {
    "console-usability.css": "text/css; charset=utf-8",
    "console-usability.js": "text/javascript; charset=utf-8",
    "provider-easy-setup.css": "text/css; charset=utf-8",
    "provider-easy-setup.js": "text/javascript; charset=utf-8",
}
_AI_SETTING_ENVS = {"TONMEN_AI_PROVIDER", "TONMEN_AI_MODEL", "TONMEN_AI_POOL"}
_API_KEY_ENVS = {"OPENAI_API_KEY", "DEEPSEEK_API_KEY", "MISTRAL_API_KEY"}


def _friendly_error(message: str) -> tuple[str, str | None]:
    text = str(message or "").strip()
    lower = text.lower()
    if "mission is not waiting for approval" in lower:
        return "当前任务已经不在等待批准状态。请刷新任务状态后再操作。", "刷新任务"
    if "fresh approval grant required" in lower:
        return "上一次授权已经失效。请重新点击“批准并继续”生成新的单次授权。", "重新批准"
    if "explicit approval grant required" in lower or "requires approval grant" in lower:
        return "这一步属于主动验证，需要你确认后才能继续。", "批准并继续"
    match = re.search(r"execution timed out after (\d+) seconds", lower)
    if match:
        return f"扫描运行超过 {match.group(1)} 秒，已停止并保留现有证据。需要时可重新批准后重试。", "查看证据或重新批准"
    if "not configured" in lower and "_api_key" in lower:
        return "还没有配置这个 AI Provider 的 API Key。可在 Provider Hub 直接粘贴并保存。", "打开 Provider Hub"
    if "is not installed" in lower:
        return "所需的官方 CLI 还没有安装。安装完成后再点“网页登录/检查连接”。", "查看安装提示"
    return text, None


class DashboardState(PreflightDashboardState):
    """Console state focused on immediate feedback and no-shell AI setup."""

    def __init__(self, config: TonmenConfig) -> None:
        self._explicit_ai_env = {name for name in _AI_SETTING_ENVS if os.getenv(name, "").strip()}
        self._explicit_secret_env = {name for name in _API_KEY_ENVS if os.getenv(name, "").strip()}
        apply_local_ai_environment()
        super().__init__(config)
        self._approval_jobs: dict[str, dict[str, Any]] = {}

    def provider_hub(self) -> dict[str, Any]:
        payload = super().provider_hub()
        payload["local_settings"] = public_settings()
        payload["configuration_precedence"] = {
            "environment_overrides_local_settings": True,
            "explicit_setting_envs": sorted(self._explicit_ai_env),
        }
        providers = []
        hub = ProviderHub()
        for provider in payload.get("providers", []):
            item = dict(provider)
            provider_id = str(item.get("id") or "")
            spec = hub.spec(provider_id)
            if spec.api_key_env:
                item["local_secret"] = public_secret_status(spec.api_key_env)
                item["secret_env_overrides_local"] = spec.api_key_env in self._explicit_secret_env
            else:
                item["login_command"] = list(spec.login_command)
                item["setup_hint"] = (
                    f"安装官方 {spec.executable} CLI 后，在此点击网页登录。TONMEN 不读取该 CLI 的凭据文件。"
                    if not item.get("installed")
                    else "官方 CLI 已安装；可点击网页登录，然后检查连接。"
                )
            providers.append(item)
        payload["providers"] = providers
        return payload

    def save_provider_key(self, provider_id: str, value: str) -> dict[str, Any]:
        hub = ProviderHub()
        spec = hub.spec(provider_id)
        if spec.auth_mode != "api_key" or not spec.api_key_env:
            raise ValueError("该 Provider 使用官方网页登录，不接受 API Key")
        set_secret(spec.api_key_env, value)
        if spec.api_key_env not in self._explicit_secret_env:
            os.environ[spec.api_key_env] = str(value).strip()
        self.events.publish("ai.provider_key_updated", provider=provider_id, configured=True, secret_exposed=False)
        return {
            "provider": provider_id,
            "configured": True,
            "source": "environment" if spec.api_key_env in self._explicit_secret_env else "local_store",
            "environment_override": spec.api_key_env in self._explicit_secret_env,
            "secret_exposed": False,
        }

    def clear_provider_key(self, provider_id: str) -> dict[str, Any]:
        hub = ProviderHub()
        spec = hub.spec(provider_id)
        if spec.auth_mode != "api_key" or not spec.api_key_env:
            raise ValueError("该 Provider 不使用 API Key")
        removed = clear_secret(spec.api_key_env)
        if spec.api_key_env not in self._explicit_secret_env:
            os.environ.pop(spec.api_key_env, None)
        still_configured = bool(os.getenv(spec.api_key_env, "").strip())
        self.events.publish("ai.provider_key_updated", provider=provider_id, configured=still_configured, secret_exposed=False)
        return {
            "provider": provider_id,
            "stored_key_removed": removed,
            "configured": still_configured,
            "environment_override": spec.api_key_env in self._explicit_secret_env,
            "secret_exposed": False,
        }

    def update_ai_configuration(self, data: dict[str, Any]) -> dict[str, Any]:
        lead_enabled = data.get("lead_enabled") if "lead_enabled" in data else None
        lead_model = data.get("lead_model") if "lead_model" in data else None
        pool = data.get("pool") if "pool" in data else None
        if pool is not None and not isinstance(pool, list):
            raise ValueError("pool must be a list")
        stored = update_settings(lead_enabled=lead_enabled, lead_model=lead_model, pool=pool)
        if lead_enabled is not None and "TONMEN_AI_PROVIDER" not in self._explicit_ai_env:
            os.environ["TONMEN_AI_PROVIDER"] = "openai" if bool(lead_enabled) else "disabled"
        if lead_model is not None and "TONMEN_AI_MODEL" not in self._explicit_ai_env:
            os.environ["TONMEN_AI_MODEL"] = str(lead_model).strip()
        if pool is not None and "TONMEN_AI_POOL" not in self._explicit_ai_env:
            os.environ["TONMEN_AI_POOL"] = ",".join(str(item).strip().lower() for item in pool if str(item).strip())
        self.events.publish("ai.local_settings_updated", secret_exposed=False)
        return {
            "settings": stored,
            "environment_overrides": sorted(self._explicit_ai_env),
            "applied_without_restart": True,
            "secret_exposed": False,
        }

    def approval_status(self, run_id: str) -> dict[str, Any]:
        with self._lock:
            return dict(self._approval_jobs.get(run_id) or {"run_id": run_id, "status": "idle"})

    def _run_approved_mission(self, run_id: str, plan, run, waiting, token: str) -> None:
        try:
            result = MissionLoop(self.runtime, self._policy_from_run(run), checkpoint=self._checkpoint).resume(
                plan,
                run,
                approval_tokens={waiting.id: token},
            )
            self._checkpoint(plan, result.run)
            with self._lock:
                self._approval_jobs[run_id] = {
                    "run_id": run_id,
                    "status": "completed",
                    "state": result.run.state.value,
                    "stop_reason": result.stop_reason.value,
                    "message": "批准后的步骤已经执行完成。",
                }
            self.events.publish("approval.background_completed", mission_id=run_id, state=result.run.state.value)
        except Exception as exc:
            friendly, action = _friendly_error(str(exc))
            with self._lock:
                self._approval_jobs[run_id] = {
                    "run_id": run_id,
                    "status": "failed",
                    "message": friendly,
                    "next_action": action,
                    "technical": str(exc)[:500],
                }
            self.events.publish("approval.background_failed", mission_id=run_id, error=str(exc)[:300])

    def approve_mission(self, run_id: str) -> dict[str, Any]:
        with self._lock:
            existing = self._approval_jobs.get(run_id)
            if existing and existing.get("status") in {"accepted", "running"}:
                return {**existing, "duplicate_suppressed": True}
            plan, run = self.chronicle.load(run_id)
            if run.state is not MissionRunState.WAITING_APPROVAL:
                raise ValueError("mission is not waiting for approval")
            waiting = _waiting_step(plan, run)
            if waiting is None:
                raise ValueError("approval-gated step is missing")
            self._require_tool_ready(waiting.tool, mission_id=run.id, step_id=waiting.id)
            if self.runtime.approvals is None:
                raise ValueError("approval store is unavailable")
            grant = self.runtime.approvals.issue(tool=waiting.tool, target=waiting.target)
            accepted = {
                "run_id": run_id,
                "status": "accepted",
                "state": run.state.value,
                "tool": waiting.tool,
                "message": "已受理。主动验证正在后台执行，你可以继续查看页面，状态会自动更新。",
                "approval_token_exposed": False,
            }
            self._approval_jobs[run_id] = accepted
            self.events.publish(
                "approval.granted",
                mission_id=run.id,
                plan_id=plan.id,
                target=run.target,
                step_id=waiting.id,
                tool=waiting.tool,
                step_target=waiting.target,
            )
            thread = threading.Thread(
                target=self._run_approved_mission,
                args=(run_id, plan, run, waiting, grant.token),
                name=f"tonmen-approve-{run_id[:8]}",
                daemon=True,
            )
            thread.start()
            self._approval_jobs[run_id] = {**accepted, "status": "running"}
            return dict(self._approval_jobs[run_id])


class UsabilityDashboardHandler(MissionPreflightDashboardHandler):
    """Adds non-blocking approval and local AI setup endpoints."""

    def _send_bytes(self, status: int, content_type: str, payload: bytes, *, cache: str = "no-store") -> None:
        try:
            super()._send_bytes(status, content_type, payload, cache=cache)
        except (BrokenPipeError, ConnectionResetError):
            return

    def _error(self, status: int, message: str) -> None:
        friendly, action = _friendly_error(message)
        payload: dict[str, Any] = {"error": friendly, "technical": str(message)[:500]}
        if action:
            payload["next_action"] = action
        self._json(status, payload)

    def _index(self) -> bytes:
        text = super()._index().decode("utf-8")
        if "/assets/console-usability.css" not in text:
            text = text.replace("</head>", '  <link rel="stylesheet" href="/assets/console-usability.css?v=easy-1">\n</head>')
        if "/assets/console-usability.js" not in text:
            text = text.replace("</body>", '  <script src="/assets/console-usability.js?v=easy-1"></script>\n</body>')
        return text.encode("utf-8")

    def _provider_index(self) -> bytes:
        text = super()._provider_index().decode("utf-8")
        if "/assets/provider-easy-setup.css" not in text:
            text = text.replace("</head>", '  <link rel="stylesheet" href="/assets/provider-easy-setup.css?v=easy-1">\n</head>')
        if "/assets/provider-easy-setup.js" not in text:
            text = text.replace("</body>", '  <script src="/assets/provider-easy-setup.js?v=easy-1"></script>\n</body>')
        return text.encode("utf-8")

    def do_GET(self) -> None:
        path = urlparse(self.path).path.rstrip("/") or "/"
        if path.startswith("/assets/"):
            name = unquote(path.removeprefix("/assets/"))
            content_type = _USABILITY_ASSETS.get(name)
            if content_type is not None:
                payload = resources.files("tonmen.dashboard.static").joinpath(name).read_bytes()
                self._send_bytes(200, content_type, payload, cache="no-store")
                return
        if path.startswith("/api/missions/") and path.endswith("/approval-status"):
            run_id = unquote(path.split("/")[3])
            self._json(200, self.server.state.approval_status(run_id))
            return
        super().do_GET()

    def do_POST(self) -> None:
        path = urlparse(self.path).path.rstrip("/")
        parts = path.split("/")
        is_key_action = len(parts) == 6 and parts[1:4] == ["api", "ai", "providers"] and parts[5] in {"key", "clear-key"}
        if path != "/api/ai/config" and not is_key_action:
            super().do_POST()
            return
        if not self._csrf_ok():
            self._error(403, "invalid local CSRF token or origin")
            return
        try:
            data = self._read_json()
            if path == "/api/ai/config":
                self._json(200, self.server.state.update_ai_configuration(data))
                return
            provider_id = unquote(parts[4]).strip().lower()
            if parts[5] == "key":
                value = str(data.get("value", "")).strip()
                if not value:
                    raise ValueError("请输入 API Key")
                self._json(200, self.server.state.save_provider_key(provider_id, value))
            else:
                self._json(200, self.server.state.clear_provider_key(provider_id))
        except (ValueError, OSError, KeyError, json.JSONDecodeError) as exc:
            self._error(400, str(exc))
        except Exception as exc:
            self._error(500, f"AI configuration error: {exc}")


class UsabilityDashboardServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, state: DashboardState):
        self.state = state
        self.csrf_token = secrets.token_urlsafe(32)
        super().__init__(address, UsabilityDashboardHandler)


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
    server = UsabilityDashboardServer((host, bind_port), DashboardState(config))
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
