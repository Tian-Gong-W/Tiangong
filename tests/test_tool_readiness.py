from __future__ import annotations

from tonmen.agents import MissionCoordinator
from tonmen.core.config import TonmenConfig
from tonmen.core.runtime import TonmenRuntime
from tonmen.missions import MissionPlan, MissionStep, MissionRunState, StepExecutionState
from tonmen.tools import RiskLevel, ToolReadiness
from tonmen.tools.adapters.nuclei import NucleiAdapter


def _nuclei_plan() -> MissionPlan:
    step = MissionStep.create(
        tool="nuclei",
        target="localhost",
        parameters={"severity": ("medium", "high"), "rate_limit": 10, "timeout": 10},
        risk=int(RiskLevel.VALIDATION),
        requires_approval=True,
        rationale="Validate only after explicit approval.",
    )
    return MissionPlan.create("localhost", [step])


def test_nuclei_adapter_reports_missing_templates(monkeypatch, tmp_path):
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/nuclei" if name == "nuclei" else None)
    monkeypatch.setenv("TONMEN_NUCLEI_TEMPLATES", str(tmp_path / "missing-templates"))

    readiness = NucleiAdapter().readiness()

    assert readiness.ready is False
    assert readiness.code == "missing_templates"
    assert "nuclei -ut" in (readiness.remediation or "")


def test_nuclei_adapter_reports_ready_with_yaml_templates(monkeypatch, tmp_path):
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/nuclei" if name == "nuclei" else None)
    root = tmp_path / "nuclei-templates" / "http"
    root.mkdir(parents=True)
    (root / "demo.yaml").write_text("id: demo\n", encoding="utf-8")
    monkeypatch.setenv("TONMEN_NUCLEI_TEMPLATES", str(tmp_path / "nuclei-templates"))

    readiness = NucleiAdapter().readiness()

    assert readiness.ready is True
    assert readiness.code == "ready"
    assert readiness.metadata["templates_path"] == str((tmp_path / "nuclei-templates").resolve())


def test_approved_validation_stays_waiting_when_preflight_is_blocked(monkeypatch, tmp_path):
    runtime = TonmenRuntime.sentinel(TonmenConfig(workspace=tmp_path, allowed_targets=("localhost",)))
    coordinator = MissionCoordinator(runtime)
    plan = _nuclei_plan()
    run = coordinator.run(plan)
    step = plan.steps[0]
    grant = runtime.approvals.issue(tool=step.tool, target=step.target)

    adapter = runtime.registry.get("nuclei")
    monkeypatch.setattr(
        adapter,
        "readiness",
        lambda: ToolReadiness(
            False,
            "missing_templates",
            "Nuclei binary is ready but templates are missing",
            remediation="Run `nuclei -ut`.",
        ),
    )

    resumed = coordinator.resume(plan, run, approval_tokens={step.id: grant.token})

    assert resumed.state is MissionRunState.WAITING_APPROVAL
    assert resumed.steps[0].state is StepExecutionState.WAITING_APPROVAL
    assert resumed.steps[0].job_id is None
    assert resumed.steps[0].metadata["preflight"]["code"] == "missing_templates"
    assert "templates are missing" in (resumed.steps[0].error or "")
    assert runtime.approvals._grants == {}
