from __future__ import annotations

import subprocess
import sys

from tonmen.agents import MissionPlanner
from tonmen.core.config import TonmenConfig
from tonmen.core.runtime import TonmenRuntime
from tonmen.dashboard.server import _STATIC_TYPES, DashboardState
from tonmen.events import EventBus
from tonmen.execution import ToolExecutor
from tonmen.jobs import JobManager
from tonmen.loop import MissionLoop
from tonmen.policy import PolicyEngine
from tonmen.tools import RiskLevel, ToolAdapter, ToolRegistry, ToolRequest, ToolSpec


class StreamingAdapter(ToolAdapter):
    spec = ToolSpec(name="stream-demo", category="test", description="streaming test adapter", risk=RiskLevel.DISCOVERY)

    def validate(self, request: ToolRequest) -> None:
        if request.target != "local-test":
            raise ValueError("wrong target")

    def build_argv(self, request: ToolRequest):
        return (sys.executable, "-u", "-c", "import sys; print('alpha', flush=True); print('omega', file=sys.stderr, flush=True)")


def test_event_bus_cursor_read_and_wait():
    bus = EventBus(capacity=64)
    first = bus.publish("one", value=1)
    second = bus.publish("two", value=2)
    assert first.cursor == 1
    assert second.cursor == 2
    assert [event.type for event in bus.read_after(0)] == ["one", "two"]
    assert [event.type for event in bus.wait_after(1, timeout=0)] == ["two"]
    assert bus.wait_after(2, timeout=0) == []


def test_executor_streams_stdout_stderr_events_with_context():
    bus = EventBus(capacity=128)
    registry = ToolRegistry(); registry.register(StreamingAdapter())
    executor = ToolExecutor(registry, PolicyEngine(), timeout_seconds=5, events=bus)
    outcome = executor.execute(ToolRequest(tool="stream-demo", target="local-test", context={"mission_id": "mission-1", "step_id": "step-1"}))
    events = bus.read_after(0)
    output = [event for event in events if event.type == "tool.output"]
    assert outcome.result.success is True
    assert "alpha" in outcome.evidence.stdout
    assert "omega" in outcome.evidence.stderr
    assert any(event.data["stream"] == "stdout" and "alpha" in event.data["chunk"] for event in output)
    assert any(event.data["stream"] == "stderr" and "omega" in event.data["chunk"] for event in output)
    assert all(event.data["mission_id"] == "mission-1" and event.data["step_id"] == "step-1" for event in output)
    assert events[0].type == "tool.started"
    assert events[-1].type == "tool.completed"


def _runtime(tmp_path, bus: EventBus):
    runtime = TonmenRuntime.sentinel(TonmenConfig(workspace=tmp_path, allowed_targets=("localhost",)), events=bus)
    outputs = {
        "nmap": "Nmap scan report for localhost\nHost is up.\n80/tcp open http\n",
        "httpx": "https://localhost [200] [Welcome] [nginx]\n",
    }
    def fake_runner(argv, **kwargs):
        return subprocess.CompletedProcess(argv, 0, stdout=outputs.get(argv[0], ""), stderr="")
    runtime.executor._runner = fake_runner
    runtime.jobs = JobManager(runtime.executor)
    return runtime


def test_mission_loop_publishes_semantic_lifecycle_events(tmp_path):
    bus = EventBus(capacity=256)
    runtime = _runtime(tmp_path, bus)
    plan = MissionPlanner(runtime).plan("localhost")
    result = MissionLoop(runtime).run(plan)
    events = bus.read_after(0)
    types = [event.type for event in events]
    assert "mission.started" in types
    assert types.count("step.started") == 3
    assert types.count("evidence.created") == 3
    assert "intelligence.created" in types
    assert "reasoning.decided" in types
    assert "approval.required" in types
    assert "loop.iteration" in types
    assert "loop.stopped" in types
    tool_starts = [event for event in events if event.type == "tool.started"]
    assert len(tool_starts) == 3
    assert all(event.data["mission_id"] == result.run.id for event in tool_starts)
    assert {event.data["step_id"] for event in tool_starts} == {plan.steps[0].id, plan.steps[1].id, plan.steps[2].id}
    assert result.run.state.value == "waiting_approval"


def test_dashboard_event_stream_and_assets(tmp_path):
    config = TonmenConfig(workspace=tmp_path, config_path=tmp_path / "tonmen.toml")
    state = DashboardState(config)
    state.events.publish("demo.changed", value=7)
    payload = state.event_stream(0, timeout=0, limit=20)
    assert payload["cursor"] == 1
    assert payload["events"][0]["type"] == "demo.changed"
    assert payload["events"][0]["data"]["value"] == 7
    assert _STATIC_TYPES["events.js"].startswith("text/javascript")
    assert _STATIC_TYPES["events.css"].startswith("text/css")
