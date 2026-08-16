from __future__ import annotations

import subprocess

from tonmen.agents import MissionCoordinator, MissionPlanner
from tonmen.chronicle import ChronicleStore
from tonmen.core.config import TonmenConfig
from tonmen.core.runtime import TonmenRuntime
from tonmen.jobs import JobManager
from tonmen.missions import MissionRunState, StepExecutionState


def _runtime(tmp_path, calls):
    runtime = TonmenRuntime.sentinel(TonmenConfig(workspace=tmp_path))

    def fake_runner(argv, **kwargs):
        calls.append(list(argv))
        return subprocess.CompletedProcess(argv, 0, stdout=f"{argv[0]} output\n", stderr="")

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
    assert len(loaded_run.evidence) == 2
    assert loaded_run.evidence[0].stdout.startswith("nmap output")
    assert len(loaded_run.observations) == 2
    assert len(loaded_run.graph.nodes) == len(run.graph.nodes)
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
    assert second_calls[0][0] == "nuclei"
    assert len(loaded_run.evidence) == 3


def test_chronicle_rejects_path_traversal_ids(tmp_path):
    store = ChronicleStore(tmp_path)
    try:
        store.load("../secrets")
    except ValueError as exc:
        assert "invalid mission run id" in str(exc)
    else:
        raise AssertionError("chronicle must reject unsafe run ids")
