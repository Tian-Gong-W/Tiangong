from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone

import pytest

from tonmen.core.config import TonmenConfig
from tonmen.core.runtime import TonmenRuntime
from tonmen.execution import ExecutionDenied
from tonmen.policy import ApprovalStore, PolicyEngine, TargetScope
from tonmen.tools import ToolReadiness, ToolRegistry, ToolRequest
from tonmen.tools.adapters import HttpxAdapter, NucleiAdapter
from tonmen.workers import (
    DispatchEnvelope,
    RemoteWorkerExecutor,
    WorkerPool,
    WorkerService,
    WorkerSpec,
    WorkerTransportError,
    validate_worker_bind_host,
)

_SECRET = "worker-test-secret-0123456789-ABCDEFGHIJ"


def _ready():
    return ToolReadiness(True, "ready", "test ready")


def _response(worker_id: str, *, tool: str = "httpx", exit_code: int = 0):
    now = datetime.now(timezone.utc).isoformat()
    return {
        "ok": True,
        "job_id": "remote-job",
        "worker": {"id": worker_id, "region": "uae", "tags": ["web"]},
        "result": {
            "tool": tool,
            "success": exit_code == 0,
            "summary": "execution completed",
            "evidence": {"timed_out": False},
        },
        "evidence": {
            "id": "evidence-remote",
            "tool": tool,
            "target": "https://example.test",
            "argv": [tool, "-u", "https://example.test"],
            "exit_code": exit_code,
            "stdout": "ok",
            "stderr": "",
            "started_at": now,
            "finished_at": now,
        },
        "worker_policy": {"decision": "allow", "reason": "worker local policy"},
    }


def test_dispatch_envelope_is_bound_signed_and_short_lived():
    envelope = DispatchEnvelope.issue(
        worker_id="uae-1",
        tool="httpx",
        target="https://example.test",
        parameters={"timeout": 5},
        context={"mission_id": "m1"},
        approval_granted=False,
        control_decision="allow",
        control_reason="risk level is within autonomous policy",
        secret=_SECRET,
        ttl_seconds=60,
        now=1000,
    )

    envelope.verify(_SECRET, expected_worker_id="uae-1", now=1030)
    with pytest.raises(ValueError, match="signature"):
        envelope.verify("wrong-secret-but-still-long-enough-00000000", expected_worker_id="uae-1", now=1030)
    with pytest.raises(ValueError, match="expired"):
        envelope.verify(_SECRET, expected_worker_id="uae-1", now=1061)
    with pytest.raises(ValueError, match="different worker"):
        envelope.verify(_SECRET, expected_worker_id="eu-1", now=1030)


def test_worker_rechecks_local_scope_before_execution(tmp_path):
    config = TonmenConfig(
        workspace=tmp_path,
        allowed_targets=("127.0.0.1", "localhost"),
        denied_targets=(),
    )
    service = WorkerService(config, worker_id="uae-1", secret=_SECRET)
    envelope = DispatchEnvelope.issue(
        worker_id="uae-1",
        tool="httpx",
        target="https://outside.example.test",
        parameters={},
        context={"mission_id": "m1"},
        approval_granted=False,
        control_decision="allow",
        control_reason="control allowed",
        secret=_SECRET,
        now=1000,
    )

    with pytest.raises(PermissionError, match="outside the authorized scope"):
        service.execute(envelope.as_dict(), now=1001)


def test_worker_executes_signed_approved_validation_without_receiving_control_token(tmp_path, monkeypatch):
    config = TonmenConfig(
        workspace=tmp_path,
        allowed_targets=("127.0.0.1", "localhost", "example.test"),
        denied_targets=(),
    )
    service = WorkerService(config, worker_id="uae-1", secret=_SECRET, region="uae", tags=("web",))
    adapter = service.registry.get("nuclei")
    monkeypatch.setattr(adapter, "readiness", _ready)
    calls = []

    def runner(argv, **kwargs):
        calls.append((list(argv), dict(kwargs)))
        return subprocess.CompletedProcess(argv, 0, stdout='{"matched-at":"https://example.test"}\n', stderr="")

    service.executor._runner = runner
    envelope = DispatchEnvelope.issue(
        worker_id="uae-1",
        tool="nuclei",
        target="https://example.test",
        parameters={"severity": "high"},
        context={"mission_id": "m1", "step_id": "s1"},
        approval_granted=True,
        control_decision="require_approval",
        control_reason="higher-risk action requires approval",
        secret=_SECRET,
        now=1000,
    )
    payload = service.execute(envelope.as_dict(), now=1001)

    assert payload["ok"] is True
    assert payload["worker"]["id"] == "uae-1"
    assert calls and calls[0][1]["shell"] is False
    assert "approval_token" not in json.dumps(payload)


def test_worker_dispatch_is_idempotent_for_exact_signed_job(tmp_path, monkeypatch):
    config = TonmenConfig(
        workspace=tmp_path,
        allowed_targets=("127.0.0.1", "localhost", "example.test"),
        denied_targets=(),
    )
    service = WorkerService(config, worker_id="uae-1", secret=_SECRET)
    adapter = service.registry.get("httpx")
    monkeypatch.setattr(adapter, "readiness", _ready)
    count = {"runs": 0}

    def runner(argv, **kwargs):
        count["runs"] += 1
        return subprocess.CompletedProcess(argv, 0, stdout="ok", stderr="")

    service.executor._runner = runner
    envelope = DispatchEnvelope.issue(
        worker_id="uae-1",
        tool="httpx",
        target="https://example.test",
        parameters={},
        context={"mission_id": "m1"},
        approval_granted=False,
        control_decision="allow",
        control_reason="allowed",
        secret=_SECRET,
        now=1000,
    )
    first = service.execute(envelope.as_dict(), now=1001)
    second = service.execute(envelope.as_dict(), now=1002)

    assert first["ok"] is True
    assert second["idempotent_replay"] is True
    assert count["runs"] == 1


def test_remote_executor_health_failover_happens_before_dispatch(monkeypatch):
    monkeypatch.setenv("TONMEN_WORKER_SECRET_A", _SECRET)
    monkeypatch.setenv("TONMEN_WORKER_SECRET_B", _SECRET)
    pool = WorkerPool(
        (
            WorkerSpec("a", "http://127.0.0.1:8891", region="uae", tags=("web",), secret_env="TONMEN_WORKER_SECRET_A"),
            WorkerSpec("b", "http://127.0.0.1:8892", region="uae", tags=("web",), secret_env="TONMEN_WORKER_SECRET_B"),
        )
    )
    registry = ToolRegistry(); registry.register(HttpxAdapter())
    policy = PolicyEngine(TargetScope(("example.test",), ()))
    dispatched = []

    class Transport:
        def health(self, spec, timeout=5):
            if spec.id == "a":
                raise WorkerTransportError("offline")
            return {"ok": True, "worker": {"id": spec.id}, "tools": {"httpx": {"ready": True}}}

        def dispatch(self, spec, envelope):
            dispatched.append((spec.id, envelope))
            return _response(spec.id)

    executor = RemoteWorkerExecutor(registry, policy, pool, transport=Transport())
    outcome = executor.execute(ToolRequest(tool="httpx", target="https://example.test", context={"mission_id": "m1"}))

    assert dispatched[0][0] == "b"
    assert dispatched[0][1].context == {"mission_id": "m1"}
    assert dispatched[0][1].approval_granted is False
    assert outcome.result.evidence["worker_id"] == "b"


def test_remote_executor_consumes_approval_centrally_and_never_forwards_token(monkeypatch):
    monkeypatch.setenv("TONMEN_WORKER_SECRET_A", _SECRET)
    pool = WorkerPool((WorkerSpec("a", "http://127.0.0.1:8891", secret_env="TONMEN_WORKER_SECRET_A"),))
    registry = ToolRegistry(); registry.register(NucleiAdapter())
    approvals = ApprovalStore()
    policy = PolicyEngine(TargetScope(("example.test",), ()))
    captured = {}

    class Transport:
        def health(self, spec, timeout=5):
            return {"ok": True, "worker": {"id": spec.id}, "tools": {"nuclei": {"ready": True}}}

        def dispatch(self, spec, envelope):
            captured["envelope"] = envelope
            return _response(spec.id, tool="nuclei")

    executor = RemoteWorkerExecutor(registry, policy, pool, approvals=approvals, transport=Transport())
    request = ToolRequest(tool="nuclei", target="https://example.test", context={"mission_id": "m1"})
    grant = approvals.issue(tool="nuclei", target="https://example.test")
    outcome = executor.execute(request, approval_token=grant.token)

    envelope = captured["envelope"]
    assert envelope.approval_granted is True
    assert grant.token not in json.dumps(envelope.as_dict())
    assert outcome.policy.decision.value == "require_approval"
    assert approvals.consume(grant.token, request) is None


def test_remote_executor_does_not_cross_worker_retry_after_ambiguous_dispatch(monkeypatch):
    monkeypatch.setenv("TONMEN_WORKER_SECRET_A", _SECRET)
    monkeypatch.setenv("TONMEN_WORKER_SECRET_B", _SECRET)
    pool = WorkerPool(
        (
            WorkerSpec("a", "http://127.0.0.1:8891", secret_env="TONMEN_WORKER_SECRET_A"),
            WorkerSpec("b", "http://127.0.0.1:8892", secret_env="TONMEN_WORKER_SECRET_B"),
        )
    )
    registry = ToolRegistry(); registry.register(HttpxAdapter())
    policy = PolicyEngine(TargetScope(("example.test",), ()))
    attempts = []

    class Transport:
        def health(self, spec, timeout=5):
            return {"ok": True, "worker": {"id": spec.id}, "tools": {"httpx": {"ready": True}}}

        def dispatch(self, spec, envelope):
            attempts.append(spec.id)
            raise WorkerTransportError("timeout after POST; ambiguous")

    executor = RemoteWorkerExecutor(registry, policy, pool, transport=Transport())
    with pytest.raises(WorkerTransportError):
        executor.execute(ToolRequest(tool="httpx", target="https://example.test"))
    assert attempts == ["a"]


def test_sentinel_worker_mode_is_explicit_and_has_no_local_executor(monkeypatch, tmp_path):
    monkeypatch.setenv("TONMEN_EXECUTION_MODE", "worker")
    monkeypatch.setenv("TONMEN_WORKERS", "uae-1@http://127.0.0.1:8890#region=uae#tags=web#secret_env=TONMEN_WORKER_SECRET_UAE")
    monkeypatch.setenv("TONMEN_WORKER_SECRET_UAE", _SECRET)
    runtime = TonmenRuntime.sentinel(TonmenConfig(workspace=tmp_path))

    assert runtime.executor is not None
    assert runtime.executor.uses_local_subprocess is False
    assert runtime.workers is not None
    assert runtime.workers.workers[0].region == "uae"
    assert "Worker Pool (1)" in runtime.status_text()


def test_worker_public_status_never_exposes_shared_secret(monkeypatch):
    monkeypatch.setenv("TONMEN_WORKER_SECRET_UAE", _SECRET)
    pool = WorkerPool((WorkerSpec("uae-1", "http://127.0.0.1:8890", secret_env="TONMEN_WORKER_SECRET_UAE"),))
    rendered = json.dumps(pool.public_status())
    assert _SECRET not in rendered
    assert pool.public_status()["workers"][0]["secret_configured"] is True
    assert pool.public_status()["privacy"]["approval_tokens_sent"] is False
    assert pool.public_status()["privacy"]["raw_shell_sent"] is False


def test_worker_remote_bind_is_fail_closed():
    assert validate_worker_bind_host("127.0.0.1") == "127.0.0.1"
    with pytest.raises(ValueError, match="allow-remote-bind"):
        validate_worker_bind_host("10.0.0.8")
    assert validate_worker_bind_host("10.0.0.8", allow_remote=True) == "10.0.0.8"
    with pytest.raises(ValueError, match="all-interface"):
        validate_worker_bind_host("0.0.0.0", allow_remote=True)
