from __future__ import annotations

import subprocess

from tonmen.agents import MissionPlanner
from tonmen.core.config import TonmenConfig
from tonmen.core.runtime import TonmenRuntime
from tonmen.events import EventBus
from tonmen.jobs import JobManager
from tonmen.loop import LoopStopReason, MissionLoop


def _tool_name(argv) -> str:
    if argv and argv[0] in {"nmap", "httpx", "nuclei"}:
        return argv[0]
    if len(argv) >= 3 and argv[1:3] == ["-m", "tonmen.tools.runners.crawler"]:
        return "crawler"
    return str(argv[0]) if argv else "unknown"


def _runtime(tmp_path, *, web: bool = True):
    events = EventBus()
    runtime = TonmenRuntime.sentinel(
        TonmenConfig(workspace=tmp_path, allowed_targets=("localhost",)),
        events=events,
    )
    calls: list[str] = []

    def fake_runner(argv, **kwargs):
        tool = _tool_name(argv)
        calls.append(tool)
        outputs = {
            "nmap": (
                "Nmap scan report for localhost\n"
                "Host is up.\n"
                "PORT   STATE SERVICE\n"
                + ("80/tcp open  http\n" if web else "22/tcp open  ssh\n")
            ),
            "httpx": "https://localhost [200] [Welcome] [nginx]\n" if web else "",
            "crawler": (
                '{"type":"page","url":"https://localhost/","status":200,"title":"Welcome",'
                '"content_type":"text/html","depth":0,"bytes":120,"truncated":false}\n'
                '{"type":"summary","visited":1,"successful":1}\n'
            ),
            "nuclei": "",
        }
        return subprocess.CompletedProcess(argv, 0, stdout=outputs[tool], stderr="")

    runtime.executor._runner = fake_runner
    runtime.jobs = JobManager(runtime.executor)
    return runtime, calls, events


def _events(events: EventBus, event_type: str):
    return [event for event in events.read_after(0, limit=1000) if event.type == event_type]


def test_adaptive_host_loop_grows_plan_from_evidence_until_approval(tmp_path):
    runtime, calls, events = _runtime(tmp_path, web=True)
    seed = MissionPlanner(runtime).seed("localhost")

    assert [step.tool for step in seed.steps] == ["nmap"]

    result = MissionLoop(runtime).run(seed)

    assert result.plan is not None
    assert [step.tool for step in result.plan.steps] == ["nmap", "httpx", "crawler", "nuclei"]
    assert calls == ["nmap", "httpx", "crawler"]
    assert result.executions == 3
    assert result.stop_reason is LoopStopReason.APPROVAL_REQUIRED
    assert _events(events, "mission.completed") == []

    revisions = [node for node in result.run.graph.nodes.values() if node.kind == "planning.revision"]
    assert [node.metadata["tool"] for node in revisions] == ["httpx", "crawler", "nuclei"]
    assert all(node.metadata["execution_authority"] is False for node in revisions)
    assert all(node.metadata["rationale"] for node in revisions)
    assert all(node.metadata["expected_information_gain"] for node in revisions)


def test_explicit_web_target_skips_network_seed_and_replans_from_http_evidence(tmp_path):
    runtime, calls, events = _runtime(tmp_path, web=True)
    seed = MissionPlanner(runtime).seed("https://localhost")

    assert [step.tool for step in seed.steps] == ["httpx"]

    result = MissionLoop(runtime).run(seed)

    assert result.plan is not None
    assert [step.tool for step in result.plan.steps] == ["httpx", "crawler", "nuclei"]
    assert calls == ["httpx", "crawler"]
    assert result.stop_reason is LoopStopReason.APPROVAL_REQUIRED
    assert "nmap" not in calls
    assert _events(events, "mission.completed") == []


def test_non_web_host_does_not_grow_a_web_tool_chain(tmp_path):
    runtime, calls, events = _runtime(tmp_path, web=False)
    seed = MissionPlanner(runtime).seed("localhost")

    result = MissionLoop(runtime).run(seed)

    assert result.plan is not None
    assert [step.tool for step in result.plan.steps] == ["nmap"]
    assert calls == ["nmap"]
    assert result.stop_reason is LoopStopReason.COMPLETE
    assert not [node for node in result.run.graph.nodes.values() if node.kind == "planning.revision"]

    completed = _events(events, "mission.completed")
    assert len(completed) == 1
    assert completed[0].data["final"] is True
    assert completed[0].data["adaptive"] is True
    assert completed[0].data["steps"] == 1
