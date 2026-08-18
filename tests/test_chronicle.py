from __future__ import annotations

import json
import subprocess

from tonmen.agents import MissionCoordinator, MissionPlanner
from tonmen.chronicle import ChronicleStore
from tonmen.core.config import TonmenConfig
from tonmen.core.runtime import TonmenRuntime
from tonmen.jobs import JobManager
from tonmen.missions import MissionRunState, StepExecutionState


def _tool_name(argv) -> str:
    if argv and argv[0] in {"nmap", "httpx", "nuclei"}:
        return argv[0]
    if len(argv) >= 3 and argv[1:3] == ["-m", "tonmen.tools.runners.crawler"]:
        return "crawler"
    return str(argv[0]) if argv else "unknown"


def _runtime(tmp_path, calls):
    runtime = TonmenRuntime.sentinel(TonmenConfig(workspace=tmp_path))

    def fake_runner(argv, **kwargs):
        calls.append(list(argv))
        output = {
            "nmap": """Nmap scan report for localhost
Host is up.
PORT   STATE SERVICE VERSION
80/tcp open  http    nginx 1.24.0
""",
            "httpx": "https://localhost [200] [Welcome] [nginx]\n",
            "crawler": '{"type":"page","url":"https://localhost/","status":200,"title":"Welcome","content_type":"text/html","depth":0,"bytes":120,"truncated":false}\n{"type":"summary","visited":1,"successful":1}\n',
            "nuclei": json.dumps(
                {
                    "template-id": "demo-check",
                    "info": {"name": "Demo Exposure", "severity": "medium"},
                    "matched-at": "https://localhost/demo",
                    "type": "http",
                }
            )
            + "\n",
        }[_tool_name(argv)]
        return subprocess.CompletedProcess(argv, 0, stdout=output, stderr="")

    runtime.executor._runner = fake_runner
    runtime.jobs = JobManager(runtime.executor)
    return runtime


def test_chronicle_roundtrip_preserves_evidence_and_graph(tmp_path):
    calls = []
    runtime = _runtime(tmp_path, calls)
    plan = MissionPlanner(runtime).plan("localhost")
    run = MissionCoordinator(runtime).run(plan)
    store = ChronicleStore(tmp_path)

    path = store.save(plan, run)
    loaded_plan, loaded_run = store.load(run.id)

    assert path.exists()
    assert loaded_plan.id == plan.id
    assert loaded_run.id == run.id
    assert loaded_run.state is MissionRunState.WAITING_APPROVAL
    assert len(loaded_run.evidence) == 3
    assert loaded_run.evidence[0].stdout.startswith("Nmap scan report")
    assert loaded_run.evidence[2].tool == "crawler"
    assert len(loaded_run.observations) == 3
    assert len(loaded_run.graph.nodes) == len(run.graph.nodes)
    assert any(node.kind == "reasoning.request_approval" for node in loaded_run.graph.nodes.values())
    assert [entry.run_id for entry in store.list()] == [run.id]


def test_persisted_mission_resumes_without_replaying_discovery(tmp_path):
    first_calls = []
    first_runtime = _runtime(tmp_path, first_calls)
    plan = MissionPlanner(first_runtime).plan("localhost")
    run = MissionCoordinator(first_runtime).run(plan)
    store = ChronicleStore(tmp_path)
    store.save(plan, run)

    second_calls = []
    second_runtime = _runtime(tmp_path, second_calls)
    loaded_plan, loaded_run = store.load(run.id)
    waiting = loaded_plan.steps[-1]
    grant = second_runtime.approvals.issue(tool=waiting.tool, target=waiting.target)

    MissionCoordinator(second_runtime).resume(loaded_plan, loaded_run, approval_tokens={waiting.id: grant.token})
    store.save(loaded_plan, loaded_run)

    assert loaded_run.state is MissionRunState.SUCCEEDED
    assert all(step.state is StepExecutionState.SUCCEEDED for step in loaded_run.steps)
    assert len(second_calls) == 1
    assert _tool_name(second_calls[0]) == "nuclei"
    assert len(loaded_run.evidence) == 4


def test_chronicle_rejects_path_traversal_ids(tmp_path):
    store = ChronicleStore(tmp_path)
    try:
        store.load("../secrets")
    except ValueError as exc:
        assert "invalid mission run id" in str(exc)
    else:
        raise AssertionError("chronicle must reject unsafe run ids")
