from __future__ import annotations

import subprocess
import threading
import time

from tonmen.core.config import TonmenConfig
from tonmen.dashboard import DashboardState
from tonmen.loop import MissionLoopPolicy
from tonmen.missions import MissionRunState


def test_console_start_returns_before_scanner_finishes(tmp_path, monkeypatch):
    state = DashboardState(TonmenConfig(workspace=tmp_path, allowed_targets=("localhost",)))
    release = threading.Event()
    started = threading.Event()
    calls: list[str] = []

    monkeypatch.setattr("tonmen.tools.base.shutil.which", lambda name: f"/usr/bin/{name}")

    def fake_runner(argv, **kwargs):
        calls.append(argv[0])
        started.set()
        release.wait(timeout=3)
        if argv[0] == "nmap":
            return subprocess.CompletedProcess(
                argv,
                0,
                stdout="Nmap scan report for localhost\nHost is up.\n80/tcp open http\n",
                stderr="",
            )
        if argv[0] == "httpx":
            return subprocess.CompletedProcess(
                argv,
                0,
                stdout="https://localhost [200] [Welcome] [nginx]\n",
                stderr="",
            )
        raise AssertionError("approval-gated validation must not execute automatically")

    state.runtime.executor._runner = fake_runner

    # This timer keeps a regression from hanging the suite. If start_mission ever
    # becomes synchronous again, the call will only return after this fires and the
    # assertion below will catch it. The later started.wait is intentionally more
    # tolerant because Docker's parallel Go/Node builds can delay Python thread
    # scheduling without changing start_mission's asynchronous contract.
    fallback_release = threading.Timer(1.5, release.set)
    fallback_release.daemon = True
    fallback_release.start()

    payload = state.start_mission(
        "localhost",
        MissionLoopPolicy(max_iterations=8, max_executions=3, max_duration_seconds=30),
    )

    assert payload["background"] is True
    assert payload["stop_reason"] == "accepted_background"
    assert payload["state"] == MissionRunState.RUNNING.value
    assert not release.is_set(), "start_mission waited for scanner execution instead of returning immediately"
    assert started.wait(timeout=3), "background mission thread did not begin execution"

    release.set()
    fallback_release.cancel()

    deadline = time.monotonic() + 3
    latest = None
    while time.monotonic() < deadline:
        latest = state.mission(payload["id"])
        if latest["state"] != MissionRunState.RUNNING.value:
            break
        time.sleep(0.02)

    assert latest is not None
    assert calls[:2] == ["nmap", "httpx"]
    assert latest["state"] == MissionRunState.WAITING_APPROVAL.value
    assert latest["evidence"]
