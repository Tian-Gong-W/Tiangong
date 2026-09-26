from __future__ import annotations

import subprocess
import threading
import time

import pytest

from tonmen.core.config import TonmenConfig
from tonmen.tools import ToolReadiness, ToolRequest
from tonmen.workers import DispatchEnvelope, WorkerPool, WorkerQueueTimeout, WorkerScheduler, WorkerService, WorkerSpec
from tonmen.workers.server import WorkerBusy

_SECRET = "scheduler-worker-secret-0123456789-ABCDEFG"


def _request(**context):
    return ToolRequest(tool="httpx", target="https://example.test", context=context)


def test_worker_pool_parses_concurrency_and_exposes_capacity_without_secret(monkeypatch):
    monkeypatch.setenv("TONMEN_WORKER_SECRET_UAE", _SECRET)
    monkeypatch.setenv(
        "TONMEN_WORKERS",
        "uae-1@http://127.0.0.1:8890#region=uae#tags=web#secret_env=TONMEN_WORKER_SECRET_UAE#weight=2#concurrency=6",
    )
    pool = WorkerPool.from_env()
    worker = pool.workers[0]

    assert worker.max_concurrency == 6
    assert pool.public_status()["workers"][0]["available_slots"] == 6
    assert _SECRET not in str(pool.public_status())


def test_scheduler_waits_for_slot_and_releases_capacity(monkeypatch):
    monkeypatch.setenv("TONMEN_WORKER_SECRET_A", _SECRET)
    pool = WorkerPool((WorkerSpec("a", "http://127.0.0.1:8890", secret_env="TONMEN_WORKER_SECRET_A", max_concurrency=1),))
    scheduler = WorkerScheduler(pool, queue_timeout_seconds=1, max_queue_size=4)
    first = scheduler.acquire(_request())
    acquired = []

    def wait_for_slot():
        lease = scheduler.acquire(_request(), timeout_seconds=0.8)
        acquired.append(lease)
        scheduler.release(lease)

    thread = threading.Thread(target=wait_for_slot)
    thread.start()
    time.sleep(0.05)
    status = scheduler.public_status()
    assert status["queue_depth"] == 1
    assert status["workers"]["a"]["inflight"] == 1
    assert not acquired

    scheduler.release(first)
    thread.join(timeout=1)
    assert acquired
    assert scheduler.public_status()["workers"]["a"]["inflight"] == 0
    assert scheduler.public_status()["total_dispatched"] == 2


def test_scheduler_drain_blocks_new_jobs_without_interrupting_inflight(monkeypatch):
    monkeypatch.setenv("TONMEN_WORKER_SECRET_A", _SECRET)
    pool = WorkerPool((WorkerSpec("a", "http://127.0.0.1:8890", secret_env="TONMEN_WORKER_SECRET_A", max_concurrency=2),))
    scheduler = WorkerScheduler(pool, queue_timeout_seconds=0.1)
    active = scheduler.acquire(_request())

    drained = scheduler.set_draining("a", True)
    assert drained["draining"] is True
    assert drained["inflight"] == 1
    with pytest.raises(WorkerQueueTimeout):
        scheduler.acquire(_request(), timeout_seconds=0.05)

    scheduler.release(active)
    assert scheduler.public_status()["workers"]["a"]["inflight"] == 0
    scheduler.set_draining("a", False)
    lease = scheduler.acquire(_request(), timeout_seconds=0.1)
    scheduler.release(lease)


def test_scheduler_routes_around_saturated_worker(monkeypatch):
    monkeypatch.setenv("TONMEN_WORKER_SECRET_A", _SECRET)
    monkeypatch.setenv("TONMEN_WORKER_SECRET_B", _SECRET)
    pool = WorkerPool(
        (
            WorkerSpec("a", "http://127.0.0.1:8891", secret_env="TONMEN_WORKER_SECRET_A", max_concurrency=1),
            WorkerSpec("b", "http://127.0.0.1:8892", secret_env="TONMEN_WORKER_SECRET_B", max_concurrency=1),
        )
    )
    scheduler = WorkerScheduler(pool)
    first = scheduler.acquire(_request())
    second = scheduler.acquire(_request())

    assert {first.worker.id, second.worker.id} == {"a", "b"}
    scheduler.release(first)
    scheduler.release(second)


def test_worker_service_hard_concurrency_limit_is_reported_and_enforced(tmp_path, monkeypatch):
    config = TonmenConfig(
        workspace=tmp_path,
        allowed_targets=("127.0.0.1", "localhost", "example.test"),
        denied_targets=(),
    )
    service = WorkerService(config, worker_id="uae-1", secret=_SECRET, max_concurrency=1)
    adapter = service.registry.get("httpx")
    monkeypatch.setattr(adapter, "readiness", lambda: ToolReadiness(True, "ready", "test ready"))
    release = threading.Event()

    def runner(argv, **kwargs):
        release.wait(timeout=1)
        return subprocess.CompletedProcess(argv, 0, stdout="ok", stderr="")

    service.executor._runner = runner

    def envelope(now, mission):
        return DispatchEnvelope.issue(
            worker_id="uae-1",
            tool="httpx",
            target="https://example.test",
            parameters={},
            context={"mission_id": mission},
            approval_granted=False,
            control_decision="allow",
            control_reason="allowed",
            secret=_SECRET,
            now=now,
        )

    errors = []

    def run_first():
        try:
            service.execute(envelope(1000, "m1").as_dict(), now=1001)
        except Exception as exc:  # pragma: no cover - assertion below captures unexpected failures
            errors.append(exc)

    thread = threading.Thread(target=run_first)
    thread.start()
    deadline = time.time() + 1
    while service.health()["capacity"]["inflight"] != 1 and time.time() < deadline:
        time.sleep(0.01)

    capacity = service.health()["capacity"]
    assert capacity["inflight"] == 1
    assert capacity["max_concurrency"] == 1
    assert capacity["accepting_jobs"] is False
    with pytest.raises(WorkerBusy, match="concurrency limit"):
        service.execute(envelope(1002, "m2").as_dict(), now=1003)

    release.set()
    thread.join(timeout=1)
    assert not errors
    assert service.health()["capacity"]["inflight"] == 0
