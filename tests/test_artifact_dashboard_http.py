from __future__ import annotations

import http.client
import json
import threading

from tonmen.core.config import TonmenConfig
from tonmen.dashboard.server import DashboardState, TonmenDashboardServer


def _request(port: int, method: str, path: str, *, body: bytes = b"", headers: dict[str, str] | None = None):
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        connection.request(method, path, body=body, headers=headers or {})
        response = connection.getresponse()
        payload = response.read()
        return response.status, response.getheader("Content-Type"), payload
    finally:
        connection.close()


def test_artifact_http_api_accepts_bytes_not_server_paths_and_requires_csrf(tmp_path):
    state = DashboardState(TonmenConfig(workspace=tmp_path))
    server = TonmenDashboardServer(("127.0.0.1", 0), state)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
    sample = b"MZ" + b"\x00" * 126
    try:
        status, _, payload = _request(
            port,
            "POST",
            "/api/artifacts/inspect",
            body=sample,
            headers={
                "Content-Type": "application/octet-stream",
                "X-TONMEN-FILENAME": "..%2Fdemo.exe",
            },
        )
        assert status == 403
        assert json.loads(payload)["error"]

        status, content_type, payload = _request(
            port,
            "POST",
            "/api/artifacts/inspect",
            body=sample,
            headers={
                "Content-Type": "application/octet-stream",
                "X-TONMEN-CSRF": server.csrf_token,
                "X-TONMEN-FILENAME": "..%2Fdemo.exe",
            },
        )
        assert status == 200
        assert content_type.startswith("application/json")
        report = json.loads(payload)
        artifact_id = report["artifact_id"]
        assert report["source_name"] == "demo.exe"
        assert report["execution_performed"] is False
        assert report["stored_blob"].startswith("artifacts/blobs/")
        assert "../" not in json.dumps(report)

        status, _, payload = _request(port, "GET", "/api/artifacts")
        listing = json.loads(payload)
        assert status == 200
        assert listing["count"] == 1
        assert listing["mode"] == "static-only"
        assert listing["execution_performed"] is False

        status, _, payload = _request(port, "GET", f"/api/artifacts/{artifact_id}")
        detail = json.loads(payload)
        assert status == 200
        assert detail["integrity_verified"] is True
        assert detail["execution_performed"] is False

        status, _, payload = _request(
            port,
            "POST",
            f"/api/artifacts/{artifact_id}/delete",
            body=b"{}",
            headers={
                "Content-Type": "application/json",
                "X-TONMEN-CSRF": server.csrf_token,
            },
        )
        assert status == 200
        assert json.loads(payload)["deleted"] == artifact_id
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_artifact_http_upload_rejects_json_path_style_requests(tmp_path):
    state = DashboardState(TonmenConfig(workspace=tmp_path))
    server = TonmenDashboardServer(("127.0.0.1", 0), state)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
    try:
        status, _, payload = _request(
            port,
            "POST",
            "/api/artifacts/inspect",
            body=json.dumps({"path": "/tmp/sample.exe"}).encode(),
            headers={
                "Content-Type": "application/json",
                "X-TONMEN-CSRF": server.csrf_token,
            },
        )
        assert status == 400
        assert "application/octet-stream" in json.loads(payload)["error"]
        assert state.artifacts()["count"] == 0
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
