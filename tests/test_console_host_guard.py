from __future__ import annotations

import http.client
import threading

import pytest

from tonmen.core.config import TonmenConfig
from tonmen.dashboard import DashboardState, validate_loopback_host_header
from tonmen.dashboard.server import TonmenDashboardServer


@pytest.mark.parametrize(
    "value",
    ["localhost", "localhost:8888", "127.0.0.1", "127.0.0.1:65535", "[::1]", "[::1]:8888"],
)
def test_loopback_host_header_accepts_only_local_control_plane_names(value):
    assert validate_loopback_host_header(value) is True


@pytest.mark.parametrize(
    "value",
    [
        None,
        "",
        "example.com",
        "example.com:8888",
        "127.0.0.1.example.com",
        "user@localhost",
        "localhost/path",
        "localhost?x=1",
        "localhost:99999",
        "localhost evil.example",
    ],
)
def test_loopback_host_header_rejects_nonlocal_or_malformed_values(value):
    assert validate_loopback_host_header(value) is False


def _serve(tmp_path):
    state = DashboardState(TonmenConfig(workspace=tmp_path, allowed_targets=("localhost",)))
    server = TonmenDashboardServer(("127.0.0.1", 0), state)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def test_console_rejects_non_loopback_host_before_read_api(tmp_path):
    server, thread = _serve(tmp_path)
    try:
        connection = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=3)
        connection.request("GET", "/api/status", headers={"Host": "evil.example"})
        response = connection.getresponse()
        body = response.read().decode("utf-8")
        connection.close()

        assert response.status == 421
        assert "loopback host required" in body
        assert response.getheader("X-Frame-Options") == "DENY"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_console_accepts_loopback_host_with_bound_port(tmp_path):
    server, thread = _serve(tmp_path)
    try:
        port = server.server_address[1]
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
        connection.request("GET", "/api/status", headers={"Host": f"127.0.0.1:{port}"})
        response = connection.getresponse()
        body = response.read().decode("utf-8")
        connection.close()

        assert response.status == 200
        assert '"version"' in body
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_console_rejects_bad_host_before_csrf_processing(tmp_path):
    server, thread = _serve(tmp_path)
    try:
        connection = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=3)
        connection.request(
            "POST",
            "/api/missions/cleanup",
            body="{}",
            headers={
                "Host": "attacker.invalid",
                "Content-Type": "application/json",
                "X-TONMEN-CSRF": server.csrf_token,
            },
        )
        response = connection.getresponse()
        body = response.read().decode("utf-8")
        connection.close()

        assert response.status == 421
        assert "loopback host required" in body
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
