from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone

from tonmen.agents import MissionCoordinator, MissionPlanner
from tonmen.ai import ProviderHub
from tonmen.core.config import TonmenConfig
from tonmen.core.runtime import TonmenRuntime
from tonmen.evidence import EvidenceRecord
from tonmen.intelligence import parse_evidence
from tonmen.jobs import JobManager
from tonmen.missions import MissionRunState, StepExecutionState
from tonmen.policy import ApprovalStore, PolicyEngine
from tonmen.tools import ToolRegistry, ToolRequest
from tonmen.tools.adapters import HttpxAdapter, NucleiAdapter
from tonmen.execution import ToolExecutor


def _evidence(tool: str, stdout: str) -> EvidenceRecord:
    now = datetime.now(timezone.utc)
    return EvidenceRecord(
        id=f"e-{tool}",
        tool=tool,
        target="localhost",
        argv=(tool,),
        exit_code=0,
        stdout=stdout,
        stderr="",
        started_at=now,
        finished_at=now,
    )


def test_config_has_longer_validation_timeout_and_supports_override(tmp_path):
    config = TonmenConfig(workspace=tmp_path)
    assert config.timeout_for("httpx") == 120
    assert config.timeout_for("nmap") == 300
    assert config.timeout_for("nuclei") == 240
    assert config.max_command_timeout_seconds == 300

    path = tmp_path / "tonmen.toml"
    path.write_text(
        """[tonmen]\nworkspace = '.tonmen'\ncommand_timeout_seconds = 150\n\n[timeouts]\nnuclei = 700\nhttpx = 45\n\n[scope]\nallowed_targets = ['localhost']\ndenied_targets = []\n""",
        encoding="utf-8",
    )
    loaded = TonmenConfig.load(path)
    assert loaded.timeout_for("nuclei") == 700
    assert loaded.timeout_for("httpx") == 45
    assert loaded.timeout_for("nmap") == 300


def test_executor_uses_tool_specific_timeout_for_nuclei():
    registry = ToolRegistry()
    registry.register(NucleiAdapter())
    approvals = ApprovalStore()
    captured = {}

    def runner(argv, **kwargs):
        captured.update(kwargs)
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    executor = ToolExecutor(
        registry,
        PolicyEngine(),
        timeout_seconds=120,
        tool_timeouts={"nuclei": 900},
        runner=runner,
        approvals=approvals,
    )
    request = ToolRequest(tool="nuclei", target="https://example.com")
    grant = approvals.issue(tool="nuclei", target="https://example.com")
    outcome = executor.execute(request, approval_token=grant.token)

    assert captured["timeout"] == 900
    assert captured["shell"] is False
    assert outcome.result.evidence["timeout_seconds"] == 900


def test_httpx_disables_color_and_parser_strips_ansi():
    argv = HttpxAdapter().build_argv(ToolRequest(tool="httpx", target="https://example.com"))
    assert "-no-color" in argv

    colored = (
        "https://example.com "
        "[\x1b[32m200\x1b[0m] "
        "[\x1b[33mWelcome\x1b[0m] "
        "[\x1b[35mBootstrap:5.3.0,Cloudflare\x1b[0m]\n"
    )
    facts = parse_evidence(_evidence("httpx", colored))

    assert len(facts) == 1
    assert facts[0].data["status_code"] == 200
    assert facts[0].data["title"] == "Welcome"
    assert facts[0].data["technologies"] == ["Bootstrap:5.3.0", "Cloudflare"]
    assert "\x1b" not in facts[0].title
    assert "\x1b" not in json.dumps(dict(facts[0].data))


def test_approval_gated_timeout_returns_to_waiting_and_accepts_fresh_approval(tmp_path):
    runtime = TonmenRuntime.sentinel(TonmenConfig(workspace=tmp_path, allowed_targets=("localhost",)))
    nuclei_attempts = {"count": 0}

    def runner(argv, **kwargs):
        tool = argv[0]
        if tool == "nmap":
            return subprocess.CompletedProcess(argv, 0, stdout="Nmap scan report for localhost\nHost is up.\n80/tcp open http\n", stderr="")
        if tool == "httpx":
            return subprocess.CompletedProcess(argv, 0, stdout="https://localhost [200] [Welcome] [nginx]\n", stderr="")
        nuclei_attempts["count"] += 1
        if nuclei_attempts["count"] == 1:
            raise subprocess.TimeoutExpired(argv, kwargs["timeout"], output="partial\n", stderr="")
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    runtime.executor._runner = runner
    runtime.jobs = JobManager(runtime.executor)
    plan = MissionPlanner(runtime).plan("localhost")
    coordinator = MissionCoordinator(runtime)
    run = coordinator.run(plan)
    step = plan.steps[-1]
    first_grant = runtime.approvals.issue(tool=step.tool, target=step.target)

    coordinator.resume(plan, run, approval_tokens={step.id: first_grant.token})

    execution = run.steps[-1]
    assert run.state is MissionRunState.WAITING_APPROVAL
    assert execution.state is StepExecutionState.WAITING_APPROVAL
    assert execution.metadata["timed_out"] is True
    assert execution.metadata["timeout_seconds"] == 240
    assert execution.metadata["approval_retry_required"] is True
    assert execution.metadata["timeout_attempts"] == 1
    assert run.finished_at is None
    assert run.evidence[-1].exit_code == 124
    assert "fresh approval grant required" in execution.error

    fresh_grant = runtime.approvals.issue(tool=step.tool, target=step.target)
    coordinator.resume(plan, run, approval_tokens={step.id: fresh_grant.token})

    assert run.state is MissionRunState.SUCCEEDED
    assert execution.state is StepExecutionState.SUCCEEDED
    assert nuclei_attempts["count"] == 2


def test_provider_auto_pool_is_explicit_and_empty_pool_error_is_actionable(monkeypatch):
    for name in ("OPENAI_API_KEY", "DEEPSEEK_API_KEY", "MISTRAL_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr("tonmen.ai.hub.shutil.which", lambda _: None)
    monkeypatch.delenv("TONMEN_AI_POOL", raising=False)

    disabled = ProviderHub()
    assert disabled.pool == ()
    fallback = disabled.review(
        "evidence_verifier",
        system="evidence only",
        payload={"evidence": []},
        fallback_summary="no model pool",
        fallback_action="finalize_report",
        fallback_confidence=0.37,
    )
    assert fallback.source == "deterministic"
    assert fallback.confidence == 0.37
    assert "TONMEN_AI_POOL=auto" in (fallback.error or "")

    monkeypatch.setenv("TONMEN_AI_POOL", "auto")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    automatic = ProviderHub()
    assert automatic.pool_mode == "auto"
    assert automatic.pool == ("deepseek",)
    status = automatic.public_status()
    assert status["configuration_warning"] is None
    assert "test-key" not in json.dumps(status)
