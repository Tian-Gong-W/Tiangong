from __future__ import annotations

import hmac
import mimetypes
import os
import secrets
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from tonmen.core.config import TonmenConfig
from tonmen.dashboard.mission_workspace_server import MissionWorkspaceDashboardHandler
from tonmen.dashboard.provider_auth_state import DashboardState


def _default_dist() -> Path:
    return Path(__file__).resolve().parents[2] / "web" / "dist"


class ProductionDashboardHandler(MissionWorkspaceDashboardHandler):
    """Serve the React console and protect every control-plane API with a bearer token."""

    server: "ProductionDashboardServer"

    def _authorized(self) -> bool:
        supplied = self.headers.get("Authorization", "")
        if not supplied.startswith("Bearer "):
            return False
        return hmac.compare_digest(supplied.removeprefix("Bearer ").strip(), self.server.web_token)

    def _csrf_ok(self) -> bool:
        if not self._authorized():
            return False
        origin = self.headers.get("Origin")
        host = self.headers.get("Host", "")
        return not origin or urlparse(origin).netloc == host

    def _security_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Robots-Tag", "noindex, nofollow")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; font-src 'self' data:; connect-src 'self'; "
            "frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
        )

    def _dist_file(self, relative: str) -> Path | None:
        root = self.server.dist_dir.resolve()
        candidate = (root / relative).resolve()
        try:
            candidate.relative_to(root)
        except ValueError:
            return None
        return candidate if candidate.is_file() else None

    def _serve_file(self, path: Path, *, cache: str) -> None:
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        if content_type.startswith("text/") or content_type in {"application/javascript", "application/json"}:
            content_type += "; charset=utf-8"
        self._send_bytes(200, content_type, path.read_bytes(), cache=cache)

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/healthz":
            self._json(200, {"ok": True, "service": "tonmen-web"})
            return
        if path == "/api/auth/status":
            if self._authorized():
                self._json(200, {"authenticated": True})
            else:
                self._error(401, "invalid access token")
            return
        if path.startswith("/api/"):
            if not self._authorized():
                self._error(401, "authentication required")
                return
            super().do_GET()
            return

        relative = unquote(path).lstrip("/")
        asset = self._dist_file(relative) if relative else None
        if asset is not None:
            cache = "public, max-age=31536000, immutable" if relative.startswith("assets/") else "no-store"
            self._serve_file(asset, cache=cache)
            return
        index = self._dist_file("index.html")
        if index is None:
            self._error(503, "web/dist is missing; run the frontend build first")
            return
        self._serve_file(index, cache="no-store")

    def do_POST(self) -> None:
        if not self._authorized():
            self._error(401, "authentication required")
            return
        super().do_POST()


class ProductionDashboardServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, state: DashboardState, *, web_token: str, dist_dir: Path):
        self.state = state
        self.csrf_token = secrets.token_urlsafe(32)
        self.web_token = web_token
        self.dist_dir = dist_dir
        super().__init__(address, ProductionDashboardHandler)


def serve() -> int:
    token = os.getenv("TONMEN_WEB_TOKEN", "").strip()
    if len(token) < 16:
        raise RuntimeError("TONMEN_WEB_TOKEN must be configured with at least 16 characters")
    port = int(os.getenv("PORT", "8080"))
    if not 1 <= port <= 65535:
        raise ValueError("PORT must be within 1-65535")
    dist_dir = Path(os.getenv("TONMEN_WEB_DIST", str(_default_dist()))).resolve()
    if not (dist_dir / "index.html").is_file():
        raise RuntimeError(f"frontend build not found: {dist_dir / 'index.html'}")
    config_value = os.getenv("TONMEN_CONFIG", "").strip()
    config = TonmenConfig.default(config_value or None)
    server = ProductionDashboardServer(
        ("0.0.0.0", port),
        DashboardState(config),
        web_token=token,
        dist_dir=dist_dir,
    )
    print(f"TONMEN Mission Control listening on 0.0.0.0:{port}")
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(serve())
