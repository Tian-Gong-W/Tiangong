from __future__ import annotations

import os
import re
import subprocess
import threading
from datetime import datetime, timezone
from pathlib import Path
from time import monotonic, sleep
from typing import Any
from urllib.parse import urlparse

from .runtime_provider import ProviderHub


_ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
_URL = re.compile(r"https://[^\s<>\]\[\"']+")
_CODE = re.compile(r"(?i)(?:one[- ]time|device|user|enter)?\s*code\s*(?:is|:)?\s*([A-Z0-9]{4,}(?:-[A-Z0-9]{3,})*)")
_ALLOWED_AUTH_HOSTS = {
    "auth.openai.com",
    "accounts.x.ai",
    "grok.com",
    "x.ai",
    "accounts.google.com",
    "antigravity.google",
}
_LOGIN_COMMANDS = {
    "chatgpt": ("codex", "login", "--device-auth"),
    "grok": ("grok", "login", "--device-auth"),
    "google": ("agy",),
}
_FALLBACK_URLS = {
    "chatgpt": "https://auth.openai.com/codex/device",
    "grok": "https://accounts.x.ai/oauth2/device",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(text: str) -> str:
    return _ANSI.sub("", str(text or "")).replace("\r", "").strip()


def _allowed_url(value: str) -> str | None:
    candidate = value.rstrip(".,;)")
    try:
        parsed = urlparse(candidate)
    except ValueError:
        return None
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https":
        return None
    if host in _ALLOWED_AUTH_HOSTS or any(host.endswith(f".{allowed}") for allowed in _ALLOWED_AUTH_HOSTS):
        return candidate
    return None


class ProviderAuthBroker:
    """Launch and observe official CLI authentication without reading credentials.

    The broker captures only the public authorization URL / one-time user code that
    the CLI prints for the operator. Credential files remain owned and interpreted by
    the official CLI. Setting HOME to a persistent Railway volume makes those official
    credential stores survive web-service redeploys without TONMEN parsing tokens.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._sessions: dict[str, dict[str, Any]] = {}
        self._processes: dict[str, subprocess.Popen[str]] = {}

    @staticmethod
    def _environment(provider_id: str) -> dict[str, str]:
        env = dict(os.environ)
        home = Path(env.get("HOME") or str(Path.home())).expanduser()
        home.mkdir(parents=True, exist_ok=True)
        env["HOME"] = str(home)
        env.setdefault("NO_COLOR", "1")
        env.setdefault("TERM", "dumb")
        if provider_id == "google":
            # Antigravity documents a remote/SSH flow that prints an authorization
            # URL instead of trying to open a browser on the server.
            env.setdefault("SSH_CONNECTION", "127.0.0.1 1 127.0.0.1 1")
        return env

    @staticmethod
    def _public_session(session: dict[str, Any]) -> dict[str, Any]:
        return {
            "provider": session.get("provider"),
            "status": session.get("status"),
            "auth_url": session.get("auth_url"),
            "user_code": session.get("user_code"),
            "detail": session.get("detail"),
            "started_at": session.get("started_at"),
            "finished_at": session.get("finished_at"),
            "pid": session.get("pid"),
            "credential_values_exposed": False,
        }

    def status(self, provider_id: str) -> dict[str, Any] | None:
        provider_id = str(provider_id).strip().lower()
        with self._lock:
            session = self._sessions.get(provider_id)
            return self._public_session(session) if session else None

    def _consume(self, provider_id: str, process: subprocess.Popen[str], ready_event: threading.Event) -> None:
        try:
            stream = process.stdout
            if stream is not None:
                for raw_line in iter(stream.readline, ""):
                    line = _clean(raw_line)
                    if not line:
                        continue
                    auth_url = None
                    for candidate in _URL.findall(line):
                        auth_url = _allowed_url(candidate)
                        if auth_url:
                            break
                    code_match = _CODE.search(line)
                    user_code = code_match.group(1).upper() if code_match else None
                    with self._lock:
                        session = self._sessions.get(provider_id)
                        if session is None:
                            break
                        if auth_url and not session.get("auth_url"):
                            session["auth_url"] = auth_url
                        if user_code and not session.get("user_code"):
                            session["user_code"] = user_code
                        if auth_url or user_code:
                            session["detail"] = "在浏览器完成官方授权，然后点击“检查连接”。"
                            ready_event.set()
            return_code = process.wait()
        except Exception as exc:
            return_code = -1
            with self._lock:
                session = self._sessions.get(provider_id)
                if session:
                    session["detail"] = str(exc)[:300]
        finally:
            ProviderHub.invalidate_probe(provider_id)
            sleep(0.2)
            try:
                probe = ProviderHub().authentication_status(provider_id, timeout=4)
            except Exception as exc:
                probe = {"authenticated": False, "detail": str(exc)[:300]}
            with self._lock:
                session = self._sessions.get(provider_id)
                if session:
                    authenticated = bool(probe.get("authenticated"))
                    session["status"] = "authenticated" if authenticated else "failed"
                    session["finished_at"] = _utc_now()
                    if authenticated:
                        session["detail"] = "官方 CLI 已确认登录。"
                    elif not session.get("detail") or session.get("detail") == "正在启动官方登录流程…":
                        session["detail"] = str(probe.get("detail") or f"login exited {return_code}")[:500]
                self._processes.pop(provider_id, None)
            ready_event.set()

    def start(self, provider_id: str) -> dict[str, Any]:
        provider_id = str(provider_id).strip().lower()
        hub = ProviderHub()
        spec = hub.spec(provider_id)
        if spec.auth_mode != "browser_login":
            raise ValueError(f"{provider_id} does not use browser login")
        if not spec.executable or not hub._installed(spec):
            raise ValueError(f"{spec.executable} is not installed")

        current = hub.authentication_status(provider_id, timeout=3)
        if current.get("authenticated"):
            session = {
                "provider": provider_id,
                "status": "authenticated",
                "auth_url": None,
                "user_code": None,
                "detail": "官方 CLI 已经处于登录状态。",
                "started_at": _utc_now(),
                "finished_at": _utc_now(),
                "pid": None,
            }
            with self._lock:
                self._sessions[provider_id] = session
            return self._public_session(session)

        command = _LOGIN_COMMANDS.get(provider_id)
        if not command:
            raise ValueError(f"no supported remote login command for {provider_id}")

        with self._lock:
            existing = self._processes.get(provider_id)
            if existing and existing.poll() is None:
                return self._public_session(self._sessions[provider_id])

            session = {
                "provider": provider_id,
                "status": "waiting_user",
                "auth_url": _FALLBACK_URLS.get(provider_id),
                "user_code": None,
                "detail": "正在启动官方登录流程…",
                "started_at": _utc_now(),
                "finished_at": None,
                "pid": None,
            }
            try:
                process = subprocess.Popen(
                    list(command),
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    shell=False,
                    env=self._environment(provider_id),
                )  # noqa: S603 - fixed official CLI argv only
            except OSError as exc:
                raise ValueError(str(exc)) from exc
            session["pid"] = process.pid
            self._sessions[provider_id] = session
            self._processes[provider_id] = process

        ready_event = threading.Event()
        thread = threading.Thread(
            target=self._consume,
            args=(provider_id, process, ready_event),
            name=f"tonmen-provider-login-{provider_id}",
            daemon=True,
        )
        thread.start()

        # Device-code CLIs normally print the URL/code immediately. Wait briefly so
        # one browser click receives useful instructions while the process continues
        # polling the provider in the background.
        deadline = monotonic() + 4.0
        while monotonic() < deadline and process.poll() is None:
            if ready_event.wait(0.1):
                break
        with self._lock:
            session = self._sessions[provider_id]
            if not session.get("auth_url") and not session.get("user_code") and process.poll() is None:
                session["detail"] = "登录进程已启动；等待官方 CLI 输出授权链接。"
            return self._public_session(session)
