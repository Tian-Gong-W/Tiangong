from __future__ import annotations

import subprocess
from datetime import datetime, timedelta, timezone

import pytest

from tonmen.agents import MissionCoordinator, MissionPlanner
from tonmen.core.config import TonmenConfig
from tonmen.core.runtime import TonmenRuntime
from tonmen.evidence import GraphNode
from tonmen.execution import ExecutionDenied, ToolExecutor
from tonmen.policy import PolicyEngine
from tonmen.tools import ToolRegistry, ToolRequest
from tonmen.tools.adapters import HttpxAdapter, NucleiAdapter
from tonmen.tools.validation import validate_web_target


def test_executor_caps_each_captured_output_stream_by_bytes():
    registry = ToolRegistry()
    registry.register(HttpxAdapter())

    def fake_runner(argv, **kwargs):
        return subprocess.CompletedProcess(argv, 0, stdout="x" * 70_000, stderr="y" * 70_000)

    executor = ToolExecutor(
        registry,
        PolicyEngine(),
        runner=fake_runner,
        max_output_bytes=65_536,
    )
    outcome = executor.execute(ToolRequest(tool="httpx", target="https://example.test"))

    assert outcome.result.success is True
    assert outcome.result.evidence["output_truncated"] is True
    assert outcome.result.evidence["stdout_truncated"] is True
    assert outcome.result.evidence["stderr_truncated"] is True
    assert outcome.result.evidence["output_max_bytes_per_stream"] == 65_536
    assert "TONMEN output truncated" in outcome.evidence.stdout
    assert "TONMEN output truncated" in outcome.evidence.stderr
    assert len(outcome.evidence.stdout.encode("utf-8")) < 66_000
    assert len(outcome.evidence.stderr.encode("utf-8")) < 66_000


def test_loop_session_remaining_wall_clock_caps_tool_timeout(tmp_path):
    runtime = TonmenRuntime.sentinel(
        TonmenConfig(workspace=tmp_path, allowed_targets=("localhost",), command_timeout_seconds=120)
    )
    captured: dict[str, float] = {}

    def fake_runner(argv, **kwargs):
        captured["timeout"] = float(kwargs["timeout"])
        return subprocess.CompletedProcess(
            argv,
            0,
            stdout="Nmap scan report for localhost\nHost is up.\n22/tcp open ssh\n",
            stderr="",
        )

    runtime.executor._runner = fake_runner
    plan = MissionPlanner(runtime).seed("localhost")
    coordinator = MissionCoordinator(runtime)
    run = coordinator.start(plan)
    run.started_at = datetime.now(timezone.utc) - timedelta(seconds=0.55)
    run.graph.add_node(
        GraphNode(
            id="budget-session",
            kind="loop.session",
            label="bounded test session",
            metadata={"max_duration_seconds": 1},
        )
    )
    run.graph.link(run.id, "governed_by", "budget-session")

    coordinator.advance_once(plan, run, defer_success=True)

    assert 0 < captured["timeout"] < 0.8
    assert captured["timeout"] <= runtime.config.command_timeout_seconds
    assert run.steps[0].metadata["mission_remaining_seconds_at_start"] < 0.8


def test_nuclei_argv_binds_configured_verified_template_root(monkeypatch, tmp_path):
    root = tmp_path / "templates"
    root.mkdir()
    (root / "demo.yaml").write_text("id: demo\ninfo:\n  name: demo\n  severity: info\n", encoding="utf-8")
    monkeypatch.setenv("TONMEN_NUCLEI_TEMPLATES", str(root))
    monkeypatch.setattr("tonmen.tools.base.shutil.which", lambda name: "/usr/bin/nuclei" if name == "nuclei" else None)

    adapter = NucleiAdapter()
    readiness = adapter.readiness()
    argv = adapter.build_argv(
        ToolRequest(
            tool="nuclei",
            target="https://example.test",
            parameters={"severity": ("medium", "high"), "rate_limit": 10, "timeout": 8},
        )
    )

    assert readiness.ready is True
    assert readiness.metadata["templates_path"] == str(root.resolve())
    template_index = argv.index("-t")
    assert argv[template_index + 1] == str(root.resolve())


@pytest.mark.parametrize(
    "query",
    [
        "token=secret",
        "access_token=secret",
        "api_key=secret",
        "password=secret",
        "session=secret",
        "jwt=secret",
        "code=secret",
    ],
)
def test_web_targets_reject_credential_like_query_parameters(query):
    with pytest.raises(ValueError, match="credential-like"):
        validate_web_target(f"https://example.test/path?{query}")


def test_web_targets_continue_to_allow_non_sensitive_single_query_parameter():
    value = "https://example.test/search?page=2"
    assert validate_web_target(value) == value


def test_forge_runtime_enforces_configured_scope(tmp_path):
    runtime = TonmenRuntime.forge(
        TonmenConfig(workspace=tmp_path, allowed_targets=("localhost",))
    )

    assert runtime.scope is not None
    assert runtime.scope.is_allowed("localhost") is True
    assert runtime.scope.is_allowed("example.test") is False
    with pytest.raises(ExecutionDenied, match="authorized scope"):
        runtime.executor.execute(ToolRequest(tool="httpx", target="https://example.test"))
