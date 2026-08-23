from __future__ import annotations

import json
import subprocess
import threading
import time
from urllib.request import Request, urlopen

from tonmen.core.config import TonmenConfig
from tonmen.dashboard.mission_workspace_server import DashboardState, MissionWorkspaceDashboardServer
from tonmen.missions import MissionRunState


def _wait_until(fetch, predicate, *, timeout: float = 5.0):
    deadline = time.monotonic() + timeout
    latest = None
    while time.monotonic() < deadline:
        latest = fetch()
        if predicate(latest):
            return latest
        time.sleep(0.02)
    raise AssertionError(f"condition not reached before timeout; latest={latest!r}")


def test_production_console_full_http_mission_lifecycle(tmp_path, monkeypatch):
    """Exercise the real Console server from preflight through final report.

    The external scanner processes are replaced with deterministic runners so the
    test is reproducible in CI, but HTTP routing, CSRF, DashboardState, MissionLoop,
    Director, Chronicle, Evidence, Approval and Report paths are all production code.
    """

    monkeypatch.setattr("tonmen.tools.base.shutil.which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr("tonmen.tools.adapters.nuclei._contains_templates", lambda root: True)

    config = TonmenConfig(workspace=tmp_path, allowed_targets=("localhost",))
    state = DashboardState(config)
    calls: list[str] = []

    nuclei_record = {
        "template-id": "e2e-medium-finding",
        "info": {"name": "E2E Confirmed Exposure", "severity": "medium"},
        "host": "https://localhost",
        "ip": "127.0.0.1",
        "matched-at": "https://localhost/demo",
        "matcher-status": True,
        "type": "http",
        "request": "GET /demo HTTP/1.1\r\nHost: localhost\r\n\r\n",
        "response": "HTTP/1.1 200 OK\r\nServer: nginx\r\n\r\nconfirmed-marker\n",
    }

    def fake_runner(argv, **kwargs):
        tool = argv[0]
        calls.append(tool)
        if tool == "nmap":
            return subprocess.CompletedProcess(
                argv,
                0,
                stdout=(
                    "Nmap scan report for localhost (127.0.0.1)\n"
                    "Host is up.\n"
                    "80/tcp open http\n"
                    "443/tcp open https\n"
                ),
                stderr="",
            )
        if tool == "httpx":
            return subprocess.CompletedProcess(
                argv,
                0,
                stdout="https://localhost [200] [Welcome] [nginx]\n",
                stderr="",
            )
        if tool == "nuclei":
            return subprocess.CompletedProcess(argv, 0, stdout=json.dumps(nuclei_record) + "\n", stderr="")
        raise AssertionError(f"unexpected tool execution: {tool}")

    state.runtime.executor._runner = fake_runner

    server = MissionWorkspaceDashboardServer(("127.0.0.1", 0), state)
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"

    def get_json(path: str):
        with urlopen(f"{base}{path}", timeout=3) as response:
            assert response.status == 200
            return json.loads(response.read().decode("utf-8"))

    def post_json(path: str, payload: dict):
        request = Request(
            f"{base}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "X-TONMEN-CSRF": server.csrf_token,
            },
            method="POST",
        )
        with urlopen(request, timeout=3) as response:
            assert response.status == 200
            return json.loads(response.read().decode("utf-8"))

    try:
        # 1. Production HTML and every isolated base script are actually served.
        with urlopen(f"{base}/", timeout=3) as response:
            html = response.read().decode("utf-8")
        for name in ("app.js", "deck.js", "module-pages.js", "events.js", "history-delete.js", "reports.js"):
            assert f"/assets/{name}?v=console-p0-1" in html
            with urlopen(f"{base}/assets/{name}?v=console-p0-1", timeout=3) as response:
                source = response.read().decode("utf-8")
                assert source.strip(), f"empty production script: {name}"

        # 2. Side-effect-light preflight reaches the production readiness path.
        policy = {
            "target": "localhost",
            "max_iterations": 12,
            "max_executions": 6,
            "max_repeat_decisions": 2,
            "max_duration_seconds": 30,
            "assessment_rounds": 0,
            "subagents_per_round": 0,
        }
        preflight = post_json("/api/missions/preflight", policy)
        assert preflight["ready_to_start"] is True
        assert preflight["blockers"] == []

        # 3. Starting through HTTP returns immediately while the real Director loop
        # runs in its background thread and persists observable state.
        started = post_json("/api/missions/start", policy)
        run_id = started["id"]
        assert started["background"] is True
        assert started["stop_reason"] == "accepted_background"
        assert started["state"] == MissionRunState.RUNNING.value

        waiting = _wait_until(
            lambda: get_json(f"/api/missions/{run_id}"),
            lambda item: item["state"] != MissionRunState.RUNNING.value,
        )
        assert waiting["state"] == MissionRunState.WAITING_APPROVAL.value
        assert {item["tool"] for item in waiting["evidence"]} >= {"nmap", "httpx"}
        assert any(step["state"] == "waiting_approval" for step in waiting["steps"])
        assert waiting["workspace"]["views"] == ["exploration", "findings", "assets", "report"]

        # 4. Reasoning and event endpoints remain readable at the approval boundary.
        reason = get_json(f"/api/missions/{run_id}/reason")
        assert reason["action"] in {"request_approval", "continue", "complete"}
        events = get_json("/api/events?cursor=0&timeout=0&limit=200")
        assert any(event["type"] == "mission.started" for event in events["events"])
        assert any(event["type"] == "approval.required" for event in events["events"])

        # 5. Approval is bound server-side and resumes asynchronously without ever
        # exposing the grant token to the browser response.
        approved = post_json(f"/api/missions/{run_id}/approve", {})
        assert approved["status"] in {"accepted", "running", "completed"}
        assert approved.get("approval_token_exposed") is not True
        assert "token" not in json.dumps(approved).lower()

        approval_done = _wait_until(
            lambda: get_json(f"/api/missions/{run_id}/approval-status"),
            lambda item: item["status"] in {"completed", "failed"},
        )
        assert approval_done["status"] == "completed", approval_done

        final = _wait_until(
            lambda: get_json(f"/api/missions/{run_id}"),
            lambda item: item["state"] in {
                MissionRunState.SUCCEEDED.value,
                MissionRunState.FAILED.value,
                MissionRunState.DENIED.value,
            },
        )
        assert final["state"] == MissionRunState.SUCCEEDED.value
        assert {item["tool"] for item in final["evidence"]} >= {"nmap", "httpx", "nuclei"}
        assert any(node["kind"] == "intelligence.finding" for node in final["intelligence"])
        assert final["workspace"]["findings"]

        # 6. Final JSON + Markdown report and audit/event surfaces are consumable.
        report = get_json(f"/api/missions/{run_id}/report")
        assert isinstance(report, dict) and report
        assert "error" not in report
        with urlopen(f"{base}/api/missions/{run_id}/report?format=markdown", timeout=3) as response:
            markdown = response.read().decode("utf-8")
        assert response.status == 200
        assert markdown.strip()

        audit = get_json("/api/audit?limit=200")
        assert isinstance(audit["events"], list)
        latest_events = get_json("/api/events?cursor=0&timeout=0&limit=500")
        assert any(event["type"] == "approval.background_completed" for event in latest_events["events"])

        assert {"nmap", "httpx", "nuclei"}.issubset(set(calls))
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
