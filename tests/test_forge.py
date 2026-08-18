import subprocess

import pytest

from tonmen.core.runtime import TonmenRuntime
from tonmen.execution import ExecutionDenied, ToolExecutor
from tonmen.jobs import JobManager, JobStatus
from tonmen.policy import Decision, PolicyEngine
from tonmen.tools import ToolRegistry, ToolRequest
from tonmen.tools.adapters import CrawlerAdapter, HttpxAdapter, NmapAdapter, NucleiAdapter, register_builtin_adapters


def test_forge_registers_four_builtin_adapters():
    runtime = TonmenRuntime.forge()
    assert len(runtime.registry) == 4
    assert {adapter.spec.name for adapter in runtime.registry} == {"nmap", "httpx", "crawler", "nuclei"}


def test_nmap_builds_bounded_argv():
    adapter = NmapAdapter()
    argv = adapter.build_argv(ToolRequest(tool="nmap", target="127.0.0.1", parameters={"ports": "80,443"}))
    assert argv == ("nmap", "-sT", "-sV", "-p", "80,443", "127.0.0.1")


def test_crawler_builds_bounded_internal_runner_argv():
    adapter = CrawlerAdapter()
    request = ToolRequest(
        tool="crawler",
        target="https://example.com",
        parameters={"max_pages": 12, "max_depth": 1, "timeout": 7},
    )
    argv = adapter.build_argv(request)
    assert argv[1:4] == ("-m", "tonmen.tools.runners.crawler", "--url")
    assert "https://example.com" in argv
    assert argv[-6:] == ("--max-pages", "12", "--max-depth", "1", "--timeout", "7")
    assert adapter.readiness().ready is True


def test_crawler_rejects_unbounded_parameters():
    with pytest.raises(ValueError, match="max_pages"):
        CrawlerAdapter().build_argv(
            ToolRequest(tool="crawler", target="https://example.com", parameters={"max_pages": 1000})
        )


def test_adapter_rejects_unknown_extra_args():
    with pytest.raises(ValueError, match="unsupported parameters"):
        NmapAdapter().build_argv(
            ToolRequest(tool="nmap", target="127.0.0.1", parameters={"extra_args": "--script vuln"})
        )


def test_httpx_rejects_shell_metacharacters_in_target():
    with pytest.raises(ValueError):
        HttpxAdapter().build_argv(ToolRequest(tool="httpx", target="example.com;id"))


def test_web_adapters_reject_credentials_in_target():
    for adapter in (HttpxAdapter(), CrawlerAdapter(), NucleiAdapter()):
        with pytest.raises(ValueError, match="credentials"):
            adapter.build_argv(ToolRequest(tool=adapter.spec.name, target="https://user:secret@example.com/private"))


def test_nuclei_requires_explicit_approval():
    registry = ToolRegistry()
    registry.register(NucleiAdapter())
    executor = ToolExecutor(registry, PolicyEngine(), runner=lambda *a, **k: None)
    with pytest.raises(ExecutionDenied, match="requires approval"):
        executor.execute(ToolRequest(tool="nuclei", target="https://example.com"))


def test_executor_uses_shell_false_and_records_evidence():
    registry = ToolRegistry()
    register_builtin_adapters(registry)
    captured = {}

    def fake_runner(argv, **kwargs):
        captured["argv"] = argv
        captured.update(kwargs)
        return subprocess.CompletedProcess(argv, 0, stdout="ok", stderr="")

    executor = ToolExecutor(registry, PolicyEngine(), runner=fake_runner)
    outcome = executor.execute(ToolRequest(tool="httpx", target="https://example.com"))
    assert captured["shell"] is False
    assert captured["check"] is False
    assert outcome.result.success is True
    assert outcome.evidence.stdout == "ok"
    assert outcome.evidence.argv[0] == "httpx"


def test_nuclei_runs_only_after_approval():
    from tonmen.policy import ApprovalStore
    registry = ToolRegistry()
    registry.register(NucleiAdapter())

    def fake_runner(argv, **kwargs):
        return subprocess.CompletedProcess(argv, 0, stdout='{"matched-at":"https://example.com"}', stderr="")

    approvals = ApprovalStore()
    executor = ToolExecutor(registry, PolicyEngine(), runner=fake_runner, approvals=approvals)
    grant = approvals.issue(tool="nuclei", target="https://example.com")
    outcome = executor.execute(ToolRequest(tool="nuclei", target="https://example.com"), approval_token=grant.token)
    assert outcome.policy.decision is Decision.REQUIRE_APPROVAL
    assert outcome.result.success is True


def test_job_manager_marks_denied_validation_job():
    registry = ToolRegistry()
    registry.register(NucleiAdapter())
    manager = JobManager(ToolExecutor(registry, PolicyEngine(), runner=lambda *a, **k: None))
    job = manager.submit(ToolRequest(tool="nuclei", target="https://example.com"))
    assert job.status is JobStatus.DENIED
    assert job.error
