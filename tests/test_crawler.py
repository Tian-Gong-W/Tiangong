from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from tonmen.tools.runners.crawler import _normalize, _origin_key, crawl
from urllib.parse import urlparse


class _Handler(BaseHTTPRequestHandler):
    secondary_port = 0

    def log_message(self, fmt, *args):
        return

    def do_GET(self):
        if self.path == "/":
            body = f"""<!doctype html><title>Home</title>
            <a href='/a'>A</a>
            <a href='/deep/one'>Deep</a>
            <a href='http://127.0.0.1:{self.secondary_port}/foreign'>Other port</a>
            <form action='/submit' method='post'><input name='secret'></form>
            """.encode()
        elif self.path == "/a":
            body = b"<!doctype html><title>A</title><a href='/b'>B</a>"
        elif self.path == "/b":
            body = b"<!doctype html><title>B</title>"
        elif self.path == "/deep/one":
            body = b"<!doctype html><title>Deep</title><a href='/deep/two'>Two</a>"
        elif self.path == "/deep/two":
            body = b"<!doctype html><title>Too Deep</title>"
        elif self.path == "/submit":
            body = b"should not be reached from form action"
        else:
            self.send_response(404); self.end_headers(); return
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class _ForeignHandler(BaseHTTPRequestHandler):
    hits = 0

    def log_message(self, fmt, *args):
        return

    def do_GET(self):
        type(self).hits += 1
        body = b"foreign"
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _serve(handler):
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def test_origin_key_normalizes_default_ports_and_rejects_cross_origin():
    assert _origin_key(urlparse("https://example.com/a")) == ("https", "example.com", 443)
    assert _origin_key(urlparse("http://example.com:80/a")) == ("http", "example.com", 80)
    origin = _origin_key(urlparse("https://example.com:8443/a"))
    assert _normalize("https://example.com:8443/b#x", origin) == "https://example.com:8443/b"
    assert _normalize("https://example.com/b", origin) is None
    assert _normalize("http://example.com:8443/b", origin) is None
    assert _normalize("https://user:secret@example.com:8443/b", origin) is None


def test_crawler_stays_same_origin_respects_depth_and_ignores_forms(capsys):
    foreign, foreign_thread = _serve(_ForeignHandler)
    primary, primary_thread = _serve(_Handler)
    _Handler.secondary_port = foreign.server_address[1]
    _ForeignHandler.hits = 0
    try:
        start = f"http://127.0.0.1:{primary.server_address[1]}/"
        result = crawl(start, max_pages=10, max_depth=1, timeout=3)
        records = [json.loads(line) for line in capsys.readouterr().out.splitlines() if line.strip()]
        pages = [item for item in records if item.get("type") == "page"]
        urls = {item["url"] for item in pages}

        assert result == 0
        assert start in urls
        assert f"http://127.0.0.1:{primary.server_address[1]}/a" in urls
        assert f"http://127.0.0.1:{primary.server_address[1]}/deep/one" in urls
        assert all("/b" not in url for url in urls)
        assert all("/deep/two" not in url for url in urls)
        assert all("/submit" not in url for url in urls)
        assert _ForeignHandler.hits == 0
        summary = records[-1]
        assert summary["type"] == "summary"
        assert summary["successful"] == 3
        assert summary["visited"] == 3
    finally:
        primary.shutdown(); primary.server_close(); primary_thread.join(timeout=2)
        foreign.shutdown(); foreign.server_close(); foreign_thread.join(timeout=2)


def test_crawler_page_budget_is_hard_bound(capsys):
    primary, thread = _serve(_Handler)
    _Handler.secondary_port = 1
    try:
        start = f"http://127.0.0.1:{primary.server_address[1]}/"
        result = crawl(start, max_pages=2, max_depth=4, timeout=3)
        records = [json.loads(line) for line in capsys.readouterr().out.splitlines() if line.strip()]
        pages = [item for item in records if item.get("type") == "page"]
        assert result == 0
        assert len(pages) == 2
        assert records[-1]["visited"] == 2
    finally:
        primary.shutdown(); primary.server_close(); thread.join(timeout=2)
