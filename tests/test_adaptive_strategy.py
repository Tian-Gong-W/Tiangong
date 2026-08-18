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
    if len(argv) >= 3 and argv[1:3] == ["-m", "tonmen.tools.runners.dns_intel"]:
        return "dns-intel"
    if len(argv) >= 3 and argv[1:3] == ["-m", "tonmen.tools.runners.tls_intel"]:
        return "tls-intel"
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
            "dns-intel": (
                '{"type":"dns","host":"localhost","record_type":"A","address":"127.0.0.1",'
                '"canonical_name":null,"reverse_name":"localhost","resolved":true}\n'
                '{"type":"summary","host":"localhost","addresses":1,"resolved":true}\n'
            ),
            "httpx": "https://localhost [200] [Welcome] [nginx]\n" if web else "",
            "tls-intel": (
                '{"type":"tls","host":"localhost","port":443,"reachable":true,"version":"TLSv1.3",'
                '"cipher":"TLS_AES_256_GCM_SHA384","cipher_bits":256,"fingerprint_sha256":"demo",'
                '"subject":"CN=localhost","issuer":"CN=Local CA","sans":["localhost"]}\n'
            ),
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
    tools = [step.tool for step in result.plan.steps]
    assert tools[0] == "nmap"
    assert tools[-1] == "nuclei"
    assert set(tools) == {"nmap", "httpx", "crawler", "dns-intel", "nuclei"}
    assert calls == ["nmap", "httpx", "crawler", "dns-intel"]
    assert result.executions == 4
    assert result.stop_reason is LoopStopReason.APPROVAL_REQUIRED
    assert _events(events, "mission.completed") == []

    revisions = [node for node in result.run.graph.nodes.values() if node.kind == "planning.revision"]
    assert {node.metadata["tool"] for node in revisions} == {"httpx", "crawler", "dns-intel", "nuclei"}
    assert all(node.metadata["execution_authority"] is False for node in revisions)
    assert all(node.metadata["rationale"] for node in revisions)
    assert all(node.metadata["expected_information_gain"] for node in revisions)


def test_explicit_web_target_adds_tls_and_dns_before_validation(tmp_path):
    runtime, calls, events = _runtime(tmp_path, web=True)
    seed = MissionPlanner(runtime).seed("https://localhost")

    assert [step.tool for step in seed.steps] == ["httpx"]

    result = MissionLoop(runtime).run(seed)

    assert result.plan is not None
    tools = [step.tool for step in result.plan.steps]
    assert tools[0] == "httpx"
    assert tools[-1] == "nuclei"
    assert set(tools) == {"httpx", "crawler", "tls-intel", "dns-intel", "nuclei"}
    assert calls[0] == "httpx"
    assert calls[-1] == "dns-intel"
    assert {"crawler", "tls-intel", "dns-intel"}.issubset(calls)
    assert "nmap" not in calls
    assert "nuclei" not in calls
    assert result.stop_reason is LoopStopReason.APPROVAL_REQUIRED
    assert _events(events, "mission.completed") == []


def test_non_web_host_can_add_dns_identity_without_growing_web_chain(tmp_path):
    runtime, calls, events = _runtime(tmp_path, web=False)
    seed = MissionPlanner(runtime).seed("localhost")

    result = MissionLoop(runtime).run(seed)

    assert result.plan is not None
    tools = [step.tool for step in result.plan.steps]
    assert tools == ["nmap", "dns-intel"]
    assert calls == ["nmap", "dns-intel"]
    assert not ({"httpx", "crawler", "tls-intel", "nuclei"} & set(tools))
    assert result.stop_reason is LoopStopReason.COMPLETE

    revisions = [node for node in result.run.graph.nodes.values() if node.kind == "planning.revision"]
    assert len(revisions) == 1
    assert revisions[0].metadata["tool"] == "dns-intel"

    completed = _events(events, "mission.completed")
    assert len(completed) == 1
    assert completed[0].data["final"] is True
    assert completed[0].data["adaptive"] is True
    assert completed[0].data["steps"] == 2
