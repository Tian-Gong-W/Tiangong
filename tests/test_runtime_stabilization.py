from __future__ import annotations

import subprocess

from tonmen.agents import MissionPlanner
from tonmen.chronicle import ChronicleStore
from tonmen.core.config import TonmenConfig
from tonmen.core.runtime import TonmenRuntime
from tonmen.dashboard import DashboardState
from tonmen.execution import ToolExecutor
from tonmen.jobs import JobManager
from tonmen.loop import LoopStopReason, MissionLoop
from tonmen.missions import MissionRunState, StepExecutionState
from tonmen.policy import PolicyEngine
from tonmen.tools import ToolRegistry, ToolRequest
from tonmen.tools.adapters import NmapAdapter


def test_web_planner_uses_fast_nmap_without_service_version_detection(tmp_path):
    runtime = TonmenRuntime.sentinel(TonmenConfig(workspace=tmp_path, allowed_targets=("localhost",)))
    plan = MissionPlanner(runtime).plan("https://localhost")
    nmap_step = plan.steps[0]

    assert nmap_step.tool == "nmap"
    assert nmap_step.parameters["service_detection"] is False
    argv = runtime.registry.get("nmap").build_argv(
        ToolRequest(tool="nmap", target=nmap_step.target, parameters=nmap_step.parameters)
    )
    assert argv == ("nmap", "-sT", "-p", "80,443", "localhost")
    assert "-sV" not in argv


def test_executor_turns_timeout_into_partial_evidence():
    registry = ToolRegistry()
    registry.register(NmapAdapter())

    def timeout_runner(argv, **kwargs):
        raise subprocess.TimeoutExpired(
            cmd=argv,
            timeout=kwargs["timeout"],
            output="partial stdout\n",
            stderr="partial stderr\n",
        )

    outcome = ToolExecutor(registry, PolicyEngine(), timeout_seconds=7, runner=timeout_runner).execute(
        ToolRequest(
            tool="nmap",
            target="127.0.0.1",
            parameters={"ports": "80,443", "service_detection": False},
        )
    )

    assert outcome.result.success is False
    assert outcome.result.evidence["timed_out"] is True
    assert outcome.result.evidence["timeout_seconds"] == 7
    assert outcome.evidence.exit_code == 124
    assert outcome.evidence.stdout == "partial stdout\n"
    assert "partial stderr" in outcome.evidence.stderr
    assert "timed out after 7 seconds" in outcome.evidence.stderr


def _timeout_then_web_runtime(tmp_path):
    runtime = TonmenRuntime.sentinel(TonmenConfig(workspace=tmp_path, allowed_targets=("localhost",)))
    calls: list[list[str]] = []

    def fake_runner(argv, **kwargs):
        calls.append(list(argv))
        if argv[0] == "nmap":
            raise subprocess.TimeoutExpired(
                cmd=argv,
                timeout=kwargs["timeout"],
                output="Nmap scan report for localhost\nHost is up.\n",
                stderr="",
            )
        if argv[0] == "httpx":
            return subprocess.CompletedProcess(
                argv,
                0,
                stdout="https://localhost [200] [Welcome] [nginx]\n",
                stderr="",
            )
        raise AssertionError("approval-gated nuclei must not execute automatically")

    runtime.executor._runner = fake_runner
    runtime.jobs = JobManager(runtime.executor)
    return runtime, calls


def test_discovery_timeout_degrades_and_httpx_still_runs(tmp_path):
    runtime, calls = _timeout_then_web_runtime(tmp_path)
    plan = MissionPlanner(runtime).plan("localhost")

    result = MissionLoop(runtime).run(plan)

    assert result.stop_reason is LoopStopReason.APPROVAL_REQUIRED
    assert result.run.state is MissionRunState.WAITING_APPROVAL
    assert [step.state for step in result.run.steps] == [
        StepExecutionState.DEGRADED,
        StepExecutionState.SUCCEEDED,
        StepExecutionState.WAITING_APPROVAL,
    ]
    assert [call[0] for call in calls] == ["httpx", "nmap"]
    nmap_call = next(call for call in calls if call[0] == "nmap")
    assert "-sV" not in nmap_call
    assert result.run.steps[0].metadata["timed_out"] is True
    assert result.run.steps[0].metadata["degraded_reason"] == "discovery_timeout"
    nmap_evidence = next(item for item in result.run.evidence if item.tool == "nmap")
    assert nmap_evidence.exit_code == 124
    assert any(node.kind == "intelligence.web" for node in result.run.graph.nodes.values())


def test_degraded_timeout_survives_chronicle_and_console_payload(tmp_path):
    runtime, _ = _timeout_then_web_runtime(tmp_path)
    plan = MissionPlanner(runtime).plan("localhost")
    result = MissionLoop(runtime).run(plan)
    store = ChronicleStore(tmp_path)
    store.save(plan, result.run)

    loaded_plan, loaded_run = store.load(result.run.id)
    assert loaded_run.steps[0].state is StepExecutionState.DEGRADED
    assert loaded_run.steps[0].metadata["timed_out"] is True
    nmap_evidence = next(item for item in loaded_run.evidence if item.tool == "nmap")
    assert nmap_evidence.exit_code == 124
    assert "timed out" in nmap_evidence.stderr

    state = DashboardState(TonmenConfig(workspace=tmp_path, config_path=tmp_path / "tonmen.toml"))
    payload = state.mission(result.run.id)
    assert payload["steps"][0]["state"] == "degraded"
    assert payload["steps"][0]["metadata"]["timed_out"] is True
    nmap_payload = next(item for item in payload["evidence"] if item["tool"] == "nmap")
    assert nmap_payload["exit_code"] == 124
    assert loaded_plan.id == plan.id


def test_non_timeout_discovery_error_degrades_and_replans(tmp_path):
    runtime = TonmenRuntime.sentinel(TonmenConfig(workspace=tmp_path, allowed_targets=("localhost",)))
    calls: list[list[str]] = []

    def fake_runner(argv, **kwargs):
        calls.append(list(argv))
        return subprocess.CompletedProcess(argv, 2, stdout="", stderr="fatal nmap error\n")

    runtime.executor._runner = fake_runner
    runtime.jobs = JobManager(runtime.executor)
    plan = MissionPlanner(runtime).plan("localhost")

    result = MissionLoop(runtime).run(plan)

    assert result.stop_reason is LoopStopReason.COMPLETE
    assert result.run.state is MissionRunState.SUCCEEDED
    assert [call[0] for call in calls] == ["httpx", "nmap"]
    assert result.run.steps[0].state is StepExecutionState.DEGRADED
    assert result.run.steps[1].state is StepExecutionState.DEGRADED
    assert result.run.steps[0].metadata["degraded_reason"] == "discovery_error"
    assert result.run.steps[1].metadata["degraded_reason"] == "discovery_error"
    assert result.run.steps[2].state is StepExecutionState.SKIPPED
    assert sorted(item.exit_code for item in result.run.evidence) == [2, 2]
