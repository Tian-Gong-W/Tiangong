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
        if supplied.startswith("Bearer "):
            token = supplied.removeprefix("Bearer ").strip()
            if hmac.compare_digest(token, self.server.web_token):
                return True
        # Allow EventSource query parameter token authentication
        from urllib.parse import parse_qs
        query = parse_qs(urlparse(self.path).query)
        token_in_query = query.get("token", [""])[0]
        if token_in_query and hmac.compare_digest(token_in_query, self.server.web_token):
            return True
        return False

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
        if path == "/api/arena/status":
            if not self._authorized():
                self._error(401, "authentication required")
                return
            self._json(200, self.server.get_full_arena_payload())
            return
        if path == "/api/arena/stream":
            if not self._authorized():
                self._error(401, "authentication required")
                return
            import json, time
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()

            last_round = -1
            last_events_len = -1
            try:
                # Stream initial state immediately
                initial = self.server.get_full_arena_payload()
                self.wfile.write(f"data: {json.dumps(initial)}\n\n".encode("utf-8"))
                self.wfile.flush()
                last_round = self.server.arbiter.current_round
                last_events_len = len(self.server.arbiter.event_log)

                while True:
                    time.sleep(1.0)
                    cur_round = self.server.arbiter.current_round
                    cur_events_len = len(self.server.arbiter.event_log)
                    if cur_round != last_round or cur_events_len != last_events_len:
                        last_round = cur_round
                        last_events_len = cur_events_len
                        payload = self.server.get_full_arena_payload()
                        self.wfile.write(f"data: {json.dumps(payload)}\n\n".encode("utf-8"))
                        self.wfile.flush()
                    else:
                        self.wfile.write(b": ping\n\n")
                        self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                return
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
        path = urlparse(self.path).path
        if path == "/api/arena/simulate-round":
            try:
                _ = self._read_json()
            except Exception:
                pass
            event = self.server.run_round_simulation()
            self._json(200, {"event": event, "status": self.server.get_full_arena_payload()})
            return
        if path == "/api/arena/tactical-combat":
            import dataclasses
            body = self._read_json()
            strategist_id = str(body.get("strategist_id") or self.server.arbiter.ledger.current_leader_id or "claude-3-5-sonnet")
            target_node = str(body.get("target_node") or "foothold_access")
            result = self.server.arbiter.execute_tactical_combat(
                strategist_id=strategist_id,
                target_node=target_node,
                knowledge_hub=self.server.knowledge_hub,
            )
            self._json(200, {
                "combat_result": dataclasses.asdict(result),
                "status": self.server.get_full_arena_payload(),
            })
            return
        if path == "/api/arena/auto-mode":
            body = self._read_json()
            enable = bool(body.get("enabled", not self.server.auto_simulate))
            self.server.set_auto_simulate(enable)
            self._json(200, {"auto_simulate": self.server.auto_simulate})
            return

        super().do_POST()


class ProductionDashboardServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, state: DashboardState, *, web_token: str, dist_dir: Path):
        self.state = state
        self.csrf_token = secrets.token_urlsafe(32)
        self.web_token = web_token
        self.dist_dir = dist_dir

        from tonmen.arena import TheArbiter, ProbabilisticAttackGraph, ArenaLedger
        from tonmen.arena.strategists import StrategistObserverPool
        from tonmen.arena.mission_bridge import MissionArenaBridge
        from tonmen.infrastructure import LiveSecurityKnowledgeHub, EgressManager, SessionVault
        
        self.graph = ProbabilisticAttackGraph(goal_node_id="target_admin")
        self.graph.add_state_node("recon_info", "资产与端口发现", achieved=True)
        self.graph.add_state_node("waf_identified", "WAF 指纹识别", achieved=False)
        self.graph.add_state_node("waf_bypassed", "WAF 规则绕过", achieved=False)
        self.graph.add_state_node("service_vuln", "服务脆弱性验证", achieved=False)
        self.graph.add_state_node("foothold_access", "低权访问权限", achieved=False)
        self.graph.add_state_node("target_admin", "核心权限与数据", achieved=False)
        
        self.graph.add_transition("recon_info", "waf_identified", success_prob=0.9)
        self.graph.add_transition("waf_identified", "waf_bypassed", success_prob=0.7)
        self.graph.add_transition("recon_info", "service_vuln", success_prob=0.85)
        self.graph.add_transition("waf_bypassed", "foothold_access", success_prob=0.8)
        self.graph.add_transition("service_vuln", "foothold_access", success_prob=0.75)
        self.graph.add_transition("foothold_access", "target_admin", success_prob=0.6)
        
        self.ledger = ArenaLedger(lead_margin_threshold=0.30, lead_consecutive_rounds=2, epoch_shuffle_interval=50)
        self.arbiter = TheArbiter(graph=self.graph, ledger=self.ledger)
        
        self.arbiter.register_strategist("claude-3-5-sonnet", "Claude 3.5 Sonnet", "claude-3-5-sonnet-20241022")
        self.arbiter.register_strategist("deepseek-v3", "DeepSeek-V3", "deepseek-chat")
        self.arbiter.register_strategist("gpt-4o", "GPT-4o", "gpt-4o")
        
        self.observer_pool = StrategistObserverPool()
        self.knowledge_hub = LiveSecurityKnowledgeHub()
        self.egress_pool = EgressManager()
        self.egress_pool.add_node("node-hk-01", "socks5://198.51.100.1:1080", region="ap-east")
        self.egress_pool.add_node("node-sg-02", "socks5://203.0.113.45:1080", region="ap-southeast")
        self.egress_pool.add_node("node-us-03", "socks5://192.0.2.88:1080", region="us-west")
        self.session_vault = SessionVault()
        self.session_vault.store_credential(
            cred_id="sess-admin-jwt",
            target_domain="target-asset.local",
            cred_type="jwt",
            payload={"token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.e30.s"},
            ttl_seconds=7200,
        )
        self.mission_bridge = MissionArenaBridge(self.arbiter)

        self.auto_simulate = False
        self._auto_thread = None

        # Give runtime reference to arbiter & infrastructure
        if hasattr(self.state, "runtime") and self.state.runtime is not None:
            self.state.runtime.arbiter = self.arbiter
            self.state.runtime.knowledge_hub = self.knowledge_hub
            self.state.runtime.egress_pool = self.egress_pool
            self.state.runtime.session_vault = self.session_vault

        super().__init__(address, ProductionDashboardHandler)

    def get_full_arena_payload(self) -> dict:
        status = self.arbiter.get_status()
        current_proxy = self.egress_pool.get_stateless_proxy() or "198.51.100.1 (direct)"
        status["infrastructure"] = {
            "knowledge_hub_entries": self.knowledge_hub.count(),
            "egress_nodes": len(self.egress_pool.nodes),
            "egress_current_ip": current_proxy,
            "active_sessions": len(self.session_vault.credentials),
        }
        status["auto_simulate"] = self.auto_simulate
        return status

    def run_round_simulation(self) -> dict:
        import asyncio, random
        graph_snapshot = self.graph.snapshot()
        proposals = asyncio.run(self.observer_pool.generate_proposals(
            graph_snapshot=graph_snapshot,
            target_domain="target-asset.local",
            round_number=self.arbiter.current_round + 1,
        ))
        
        results = {}
        candidate_nodes = ["waf_identified", "waf_bypassed", "service_vuln", "foothold_access", "target_admin"]
        for p in proposals:
            unlock = []
            unlocked_candidate = [n for n in candidate_nodes if n not in self.graph.achieved_nodes]
            if unlocked_candidate and random.random() > 0.35:
                unlock = [unlocked_candidate[0]]
            
            results[p.proposal_id] = {
                "successful_actions_count": random.randint(3, 7),
                "unlocked_nodes": unlock,
                "loot_category": "access" if unlock else "info",
            }
        
        return self.arbiter.evaluate_round(proposals, results)

    def set_auto_simulate(self, enable: bool) -> None:
        self.auto_simulate = enable
        if enable and (self._auto_thread is None or not self._auto_thread.is_alive()):
            import threading
            self._auto_thread = threading.Thread(target=self._auto_loop, daemon=True)
            self._auto_thread.start()

    def _auto_loop(self) -> None:
        import time
        while self.auto_simulate:
            try:
                self.run_round_simulation()
            except Exception as e:
                print(f"[Arena Auto Loop Error] {e}")
            time.sleep(4.0)


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
