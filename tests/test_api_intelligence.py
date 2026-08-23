from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from tonmen.adaptive import build_target_profile
from tonmen.evidence import EvidenceRecord, GraphNode
from tonmen.intelligence import FactKind, parse_evidence
from tonmen.missions import MissionPlan, MissionRun
from tonmen.tools import ToolRequest
from tonmen.tools.adapters import ApiIntelAdapter
from tonmen.tools.runners.api_intel import inspect_api


class _ApiHandler(BaseHTTPRequestHandler):
    foreign_port = 0

    def log_message(self, fmt, *args):
        return

    def do_GET(self):
        if self.path == "/":
            body = f"""<!doctype html>
            <script>fetch('/api/profile'); const gql='/graphql';</script>
            <script src='/app.js'></script>
            <script src='http://127.0.0.1:{self.foreign_port}/foreign.js'></script>
            <form action='/submit' method='post'></form>
            """.encode()
            content_type = "text/html; charset=utf-8"
        elif self.path == "/app.js":
            body = b"const items='/api/items'; const docs='/openapi.json'; const version='/v1/status';"
            content_type = "application/javascript; charset=utf-8"
        else:
            self.send_response(404); self.end_headers(); return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class _ForeignHandler(BaseHTTPRequestHandler):
    hits = 0

    def log_message(self, fmt, *args):
        return

    def do_GET(self):
        type(self).hits += 1
        body = b"const foreign='/api/foreign';"
        self.send_response(200)
        self.send_header("Content-Type", "application/javascript")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _serve(handler):
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def _evidence(stdout: str) -> EvidenceRecord:
    now = datetime.now(timezone.utc)
    return EvidenceRecord(
        id="e-api",
        tool="api-intel",
        target="https://example.test",
        argv=("python", "-m", "tonmen.tools.runners.api_intel"),
        exit_code=0,
        stdout=stdout,
        stderr="",
        started_at=now,
        finished_at=now,
    )


def test_api_intel_static_runner_stays_same_origin_and_never_executes_javascript(capsys):
    foreign, foreign_thread = _serve(_ForeignHandler)
    primary, primary_thread = _serve(_ApiHandler)
    _ApiHandler.foreign_port = foreign.server_address[1]
    _ForeignHandler.hits = 0
    try:
        start = f"http://127.0.0.1:{primary.server_address[1]}/"
        result = inspect_api(start, max_scripts=8, max_bytes=131072, timeout=3)
        records = [json.loads(line) for line in capsys.readouterr().out.splitlines() if line.strip()]
        endpoints = {
            item.get("absolute_url")
            for item in records
            if item.get("type") == "api" and item.get("kind") == "endpoint"
        }

        assert result == 0
        assert f"http://127.0.0.1:{primary.server_address[1]}/api/profile" in endpoints
        assert f"http://127.0.0.1:{primary.server_address[1]}/api/items" in endpoints
        assert f"http://127.0.0.1:{primary.server_address[1]}/graphql" in endpoints
        assert f"http://127.0.0.1:{primary.server_address[1]}/v1/status" in endpoints
        assert _ForeignHandler.hits == 0

        summary = records[-1]
        assert summary["type"] == "api_summary"
        assert summary["javascript_executed"] is False
        assert summary["forms_submitted"] is False
        assert summary["cross_origin_fetches"] is False
        assert summary["scripts_fetched"] == 1
        assert "openapi" in summary["hints"]
    finally:
        primary.shutdown(); primary.server_close(); primary_thread.join(timeout=2)
        foreign.shutdown(); foreign.server_close(); foreign_thread.join(timeout=2)


def test_api_adapter_uses_observed_web_port_and_stays_adaptive_only():
    adapter = ApiIntelAdapter()
    request = ToolRequest(
        tool="api-intel",
        target="example.test",
        parameters={"max_scripts": 12, "max_bytes": 262144, "timeout": 8},
    )
    parameters = adapter.adapt_parameters(request, {"ports": (80,), "complexity": 3})
    argv = adapter.build_argv(ToolRequest(tool="api-intel", target="example.test", parameters=parameters))

    assert parameters["url"] == "http://example.test"
    assert argv[1:3] == ("-m", "tonmen.tools.runners.api_intel")
    assert adapter.spec.planning is not None
    assert adapter.spec.planning.include_in_baseline_envelope is False
    assert "javascript.endpoint.extract" in adapter.spec.capabilities


def test_api_parser_and_target_profile_close_client_api_unknown():
    stdout = "\n".join(
        [
            json.dumps({
                "type": "api",
                "kind": "endpoint",
                "endpoint": "/api/items",
                "absolute_url": "https://example.test/api/items",
                "source": "script",
                "source_url": "https://example.test/app.js",
            }),
            json.dumps({"type": "api", "kind": "hint", "hint": "openapi", "url": "https://example.test"}),
            json.dumps({
                "type": "api_summary",
                "url": "https://example.test",
                "entry_reachable": True,
                "scripts_discovered": 1,
                "scripts_fetched": 1,
                "endpoint_count": 1,
                "hints": ["openapi"],
                "javascript_executed": False,
                "forms_submitted": False,
                "cross_origin_fetches": False,
            }),
        ]
    ) + "\n"
    facts = parse_evidence(_evidence(stdout))

    assert len(facts) == 3
    assert all(fact.kind is FactKind.API for fact in facts)
    endpoint = next(fact for fact in facts if fact.data.get("kind") == "endpoint")
    assert endpoint.data["absolute_url"] == "https://example.test/api/items"
    assert endpoint.data["javascript_executed"] is False

    plan = MissionPlan.create("https://example.test", [])
    run = MissionRun.create(plan)
    run.graph.add_node(
        GraphNode(
            id="web-1",
            kind="intelligence.web",
            label="https://example.test [200]",
            metadata={"data": {"url": "https://example.test", "status_code": 200}},
        )
    )
    initial = build_target_profile(plan, run)
    assert "client_api_surface" in initial.unknowns

    for fact in facts:
        run.graph.add_node(
            GraphNode(
                id=fact.id,
                kind=f"intelligence.{fact.kind.value}",
                label=fact.title,
                metadata={
                    "source": fact.source,
                    "target": fact.target,
                    "confidence": fact.confidence,
                    "severity": fact.severity.value,
                    "data": dict(fact.data),
                },
            )
        )

    enriched = build_target_profile(plan, run)
    assert enriched.api_inspected is True
    assert enriched.api_endpoints == ("https://example.test/api/items",)
    assert "openapi" in enriched.api_hints
    assert "client_api_surface" not in enriched.unknowns
    assert any(item.key == "api_surface" for item in enriched.hypotheses)
