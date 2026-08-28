from __future__ import annotations

from tonmen.core.config import TonmenConfig
from tonmen.core.runtime import TonmenRuntime
from tonmen.evidence import GraphNode
from tonmen.missions import MissionPlan, MissionRun, MissionRunState, MissionStep, StepExecutionState
from tonmen.reasoning import MissionDirector


def _plan() -> MissionPlan:
    return MissionPlan.create(
        "localhost",
        [
            MissionStep.create(
                tool="nmap",
                target="localhost",
                parameters={"ports": "80,443", "service_detection": False},
                risk=1,
                requires_approval=False,
                rationale="network discovery",
            ),
            MissionStep.create(
                tool="httpx",
                target="https://localhost",
                parameters={"follow_redirects": False, "timeout": 10},
                risk=1,
                requires_approval=False,
                rationale="web observation",
            ),
            MissionStep.create(
                tool="nuclei",
                target="https://localhost",
                parameters={"severity": ("medium", "high", "critical"), "rate_limit": 10, "timeout": 10},
                risk=3,
                requires_approval=True,
                rationale="bounded validation",
            ),
        ],
    )


def test_pending_httpx_compatibility_target_precedes_derived_targets(tmp_path):
    runtime = TonmenRuntime.sentinel(TonmenConfig(workspace=tmp_path, allowed_targets=("localhost",)))
    plan = _plan()
    run = MissionRun.create(plan)
    run.state = MissionRunState.RUNNING
    run.steps[0].state = StepExecutionState.SUCCEEDED
    run.graph.add_node(
        GraphNode(
            id="service:https",
            kind="intelligence.service",
            label="443/tcp open ssl/http",
            metadata={
                "target": "localhost",
                "evidence_id": "e-nmap",
                "data": {"port": 443, "protocol": "tcp", "service": "ssl/http", "scanned_address": "localhost"},
            },
        )
    )

    spec = runtime.registry.get("httpx").spec
    targets = MissionDirector._candidate_targets(plan, run, spec)

    assert targets[0] == "https://localhost"


def test_pending_nuclei_compatibility_target_precedes_dynamic_origin(tmp_path):
    runtime = TonmenRuntime.sentinel(TonmenConfig(workspace=tmp_path, allowed_targets=("localhost",)))
    plan = _plan()
    run = MissionRun.create(plan)
    run.state = MissionRunState.RUNNING
    run.steps[0].state = StepExecutionState.SUCCEEDED
    run.steps[1].state = StepExecutionState.SUCCEEDED
    run.graph.add_node(
        GraphNode(
            id="web:https",
            kind="intelligence.web",
            label="https://localhost [200]",
            metadata={
                "target": "https://localhost",
                "evidence_id": "e-httpx",
                "data": {"url": "https://localhost", "status_code": 200, "technologies": []},
            },
        )
    )

    spec = runtime.registry.get("nuclei").spec
    targets = MissionDirector._candidate_targets(plan, run, spec)

    assert targets[0] == "https://localhost"
