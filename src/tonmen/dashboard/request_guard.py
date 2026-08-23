from __future__ import annotations

from urllib.parse import urlsplit

_LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}


def validate_loopback_host_header(value: str | None) -> bool:
    """Accept only a syntactically valid loopback Host header, with optional port."""
    raw = str(value or "").strip()
    if not raw or any(ch.isspace() for ch in raw):
        return False
    try:
        parsed = urlsplit(f"//{raw}")
        host = (parsed.hostname or "").lower()
        _ = parsed.port
    except ValueError:
        return False
    if parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment:
        return False
    return host in _LOOPBACK_HOSTS


def install_loopback_request_guard(handler_cls) -> None:
    """Install a fail-closed Host guard without widening the Console request surface."""
    if getattr(handler_cls, "_tonmen_loopback_request_guard", False):
        return

    original_get = handler_cls.do_GET
    original_post = handler_cls.do_POST
    original_csrf = handler_cls._csrf_ok

    def _request_host_ok(self) -> bool:
        return validate_loopback_host_header(self.headers.get("Host"))

    def _reject_host(self) -> None:
        self._error(421, "invalid Console Host header; loopback host required")

    def guarded_get(self) -> None:
        if not _request_host_ok(self):
            _reject_host(self)
            return
        original_get(self)

    def guarded_post(self) -> None:
        if not _request_host_ok(self):
            _reject_host(self)
            return
        original_post(self)

    def guarded_csrf(self) -> bool:
        return _request_host_ok(self) and bool(original_csrf(self))

    handler_cls._request_host_ok = _request_host_ok
    handler_cls.do_GET = guarded_get
    handler_cls.do_POST = guarded_post
    handler_cls._csrf_ok = guarded_csrf
    handler_cls._tonmen_loopback_request_guard = True
