import json
import subprocess
from pathlib import Path

import pytest

from tonmen.audit import AuditLog
from tonmen.core.config import TonmenConfig
from tonmen.core.runtime import TonmenRuntime
from tonmen.execution import ExecutionDenied, ToolExecutor
from tonmen.mcp import guarded_submit
from tonmen.policy import ApprovalStore, PolicyEngine, TargetScope
from tonmen.tools import ToolRegistry, ToolRequest
from tonmen.tools.adapters import HttpxAdapter, NucleiAdapter


def test_scope_supports_exact_wildcard_and_cidr():
    scope = TargetScope(("example.com", "*.lab.example.com", "10.20.0.0/16"))
    assert scope.is_allowed("https://example.com")
    assert scope.is_allowed("api.lab.example.com")
    assert scope.is_allowed("10.20.4.7")
    assert not scope.is_allowed("evil-example.com")
    assert not scope.is_allowed("10.21.0.1")


def test_deny_rule_overrides_allow_rule():
    scope = TargetScope(("*.example.com",), ("admin.example.com",))
    assert scope.is_allowed("api.example.com")
    assert not scope.is_allowed("admin.example.com")


def test_policy_denies_out_of_scope_target():
    scope = TargetScope(("localhost",))
    policy = PolicyEngine(scope)
    adapter = HttpxAdapter()
    decision = policy.evaluate(adapter.spec, ToolRequest(tool="httpx", target="https://example.com"))
    assert decision.decision.value == "deny"
    assert "outside" in decision.reason


def test_approval_grant_is_bound_and_single_use():
    store = ApprovalStore()
    request = ToolRequest(tool="nuclei", target="https://localhost")
    grant = store.issue(tool="nuclei", target="https://localhost", ttl_seconds=60)
    assert store.consume(grant.token, request) is not None
    assert store.consume(grant.token, request) is None


def test_validation_execution_requires_valid_grant(tmp_path: Path):
    registry = ToolRegistry(); registry.register(NucleiAdapter())
    approvals = ApprovalStore()
    audit = AuditLog(tmp_path / "audit.jsonl")
    policy = PolicyEngine(TargetScope(("localhost",)))

    def fake_runner(argv, **kwargs):
        return subprocess.CompletedProcess(argv, 0, stdout="{}", stderr="")

    executor = ToolExecutor(registry, policy, runner=fake_runner, approvals=approvals, audit=audit)
    request = ToolRequest(tool="nuclei", target="https://localhost")
    with pytest.raises(ExecutionDenied, match="approval"):
        executor.execute(request)
    grant = approvals.issue(tool="nuclei", target="https://localhost")
    outcome = executor.execute(request, approval_token=grant.token)
    assert outcome.result.success


def test_audit_records_denied_and_allowed_events(tmp_path: Path):
    registry = ToolRegistry(); registry.register(HttpxAdapter())
    audit_path = tmp_path / "audit.jsonl"
    policy = PolicyEngine(TargetScope(("localhost",)))

    def fake_runner(argv, **kwargs):
        return subprocess.CompletedProcess(argv, 0, stdout="ok", stderr="")

    executor = ToolExecutor(registry, policy, runner=fake_runner, audit=AuditLog(audit_path))
    with pytest.raises(ExecutionDenied):
        executor.execute(ToolRequest(tool="httpx", target="https://example.com"))
    executor.execute(ToolRequest(tool="httpx", target="https://localhost"))
    lines = [json.loads(line) for line in audit_path.read_text().splitlines()]
    assert [line["decision"] for line in lines] == ["deny", "allow"]
    assert lines[1]["evidence_id"]


def test_sentinel_defaults_to_localhost_only(tmp_path: Path):
    cfg = TonmenConfig(workspace=tmp_path)
    runtime = TonmenRuntime.sentinel(cfg)
    assert runtime.scope is not None
    assert runtime.scope.is_allowed("localhost")
    assert not runtime.scope.is_allowed("example.com")


def test_guarded_mcp_submit_cannot_self_approve(tmp_path: Path):
    cfg = TonmenConfig(workspace=tmp_path, allowed_targets=("localhost",))
    runtime = TonmenRuntime.sentinel(cfg)
    response = guarded_submit(runtime, tool="nuclei", target="https://localhost")
    assert response["status"] == "denied"
    assert "approval" in response["error"]
